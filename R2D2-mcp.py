# r2d2_mcp_server.py
# Requires: pip install bleak mcp
# Run: python r2d2_mcp_server.py
# Then point your MCP host at this server (stdio).

import asyncio
import sys
from contextlib import asynccontextmanager
from typing import Optional, Dict, List

from bleak import BleakClient, BleakScanner, BleakError

from mcp.server.mcpserver import MCPServer

SERVICE_UUID = "d9d9e9e0-aa4e-4797-8151-cb41cedaf2ad"
CHAR_UUID    = "d9d9e9e1-aa4e-4797-8151-cb41cedaf2ad"

# --- Command tables (lifted from your JS) ---
DRIVE_CONTROLS: List[str] = [
    "140202FF659D","140202FA3538","140202F6F4B4","140202F2B430","140202ED57EE",
    "140202EA2709","140202E6E685","140202E3B620","140202DF41FF","140202DA115A",
    "140202D6D0D6","140202D29052","140202CE43EF","140202CA036B","140202C5F284",
    "140202C28263","140202BE3D78","140202BA7DFC","140202B6BC70","140202B2FCF4",
    "140202AB7FEC","140202AA6FCD","140202A6AE41","140202A2EEC5","140202A1DEA6",
    "1402029E191A","1402029969FD","140202969812","14020292D896","1402028D3B48",
    "1402028A4BAF","140202897BCC",  # stop (centre)
    "1402027DD457","1402027994D3","14020276653C","1402027225B8","1402026EF605",
    "1402026DC666","1402026896C3","1402026327A8","1402026107EA","1402025CE014",
    "14020259B0B1","14020255713D","140202502198","1402024B82C2","14020249A280",
    "14020245630C","140202412388","1402023BFC55","14020239DC17","140202337D5D",
    "140202304D3E","1402022BEE64","14020229CE26","140202214F2E","140202205F0F",
    "1402021BD837","14020218E854","1402021429D8","1402020F8A82","1402020CBAE1",
    "140202070B8A"
]

TURN_SIGNALS: List[str] = [
    "140201FC00AD","140201EA725A","140201E49394","140201DF14AC","140201D9746A",
    "140201D1F562","140201CC36FE","140201C697B4","140201C0F772","140201B918CC",
    "140201B4C961","140201AE7A1A","140201A7EB33","140201A2BB96","1402019C6C0B",
    "14020196CD41","14020190AD87","1402018A1EFC",  # straight
    "14020184FF32","1402017EB167","14020178D1A1","1402017270EB","1402016C8314",
    "14020166225E","140201604298","1402015AD581","14020154344F","1402014F9715",
    "14020149F7D3","1402014246B8","1402013CD9E1","1402013548C8","140201002E3E"
]

SOUNDS: Dict[str, str] = {
    "grump":"1E011B42AA","scold":"1E011A528B","chitter":"1E011962E8","chattering":"1E011872C9",
    "i love you":"1E01178326","bleep":"1E01169307","beep":"1E0115A364","whistle":"1E0114B345",
    "descending":"1E0113C3A2","excited":"1E0112D383","cheery":"1E0111E3E0","sad":"1E0110F3C1",
    "scream!!":"1E010F101F","startup":"1E010E003E","surprise!!":"1E010C207C","story":"1E010A40BA",
    "wow!":"1E010860F8","thbt":"1E01068136","worried":"1E0104A174","dubious":"1E0102C1B2",
    "board startup!!":"1E0101F1D1","thinking":"1E0100E1F0"
}

STOP_FRAME = "140202897BCC"

# --- BLE session state ---
class R2D2Session:
    def __init__(self):
        self.client: Optional[BleakClient] = None
        self.device_address: Optional[str] = None
        self._name_hint: str = "w32 ControlHub"

    def _on_disconnect(self, _client):
        print("R2D2 disconnected — will auto-reconnect on next command.", file=sys.stderr, flush=True)
        self.client = None

    async def connect(self, address: Optional[str] = None, name_hint: Optional[str] = None, timeout: float = 15.0):
        if self.client and self.client.is_connected:
            return

        if name_hint:
            self._name_hint = name_hint

        target = None
        if address:
            target = address
        else:
            # Use find_device_by_name to scan and return the BLEDevice in one step;
            # passing the BLEDevice object (not just the address string) to BleakClient
            # avoids a macOS CoreBluetooth cache miss when connecting after a separate scan.
            target = await BleakScanner.find_device_by_name(self._name_hint, timeout=timeout)
            if target is None:
                raise RuntimeError("No suitable BLE device found. Power-cycle R2-D2 and try again.")

        self.client = BleakClient(target, disconnected_callback=self._on_disconnect)
        await self.client.connect()
        self.device_address = target.address if hasattr(target, "address") else target

        # Send a safety stop on connect
        await self.write_hex(STOP_FRAME)

    async def ensure_connected(self):
        """Reconnect silently if the BLE link dropped."""
        if not self.client or not self.client.is_connected:
            print("Auto-reconnecting to R2D2...", file=sys.stderr, flush=True)
            await self.connect()

    async def disconnect(self):
        if self.client and self.client.is_connected:
            await self.client.disconnect()
        self.client = None

    async def write_hex(self, hex_str: str):
        await self.ensure_connected()
        data = bytes.fromhex(hex_str)
        # Write with response to mirror the browser behaviour
        await self.client.write_gatt_char(CHAR_UUID, data, response=True)

SESSION = R2D2Session()

@asynccontextmanager
async def lifespan(srv):
    print("R2D2 MCP server starting...", file=sys.stderr, flush=True)
    try:
        await SESSION.connect()
        print(f"Auto-connected to R2D2 at {SESSION.device_address}", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"Auto-connect failed ({e}) — use r2d2_connect tool to connect manually", file=sys.stderr, flush=True)
    yield
    if SESSION.client and SESSION.client.is_connected:
        await SESSION.disconnect()
    print("R2D2 MCP server stopped.", file=sys.stderr, flush=True)

server = MCPServer("r2d2-mcp", lifespan=lifespan)

# ---- MCP tool registrations ----

@server.tool(name="r2d2_connect", description="Connect to the R2D2 robot over BLE. Defaults to finding 'w32 ControlHub' by name.")
async def tool_connect(address: Optional[str] = None, name_hint: Optional[str] = "w32 ControlHub", timeout: float = 15.0) -> str:
    try:
        await SESSION.connect(address=address, name_hint=name_hint, timeout=timeout)
        return f"Connected to R2D2 at {SESSION.device_address}."
    except Exception as e:
        return f"Connection failed: {type(e).__name__}: {e}"

@server.tool(name="r2d2_stop", description="Emergency/normal stop.")
async def tool_stop() -> str:
    try:
        await SESSION.write_hex(STOP_FRAME)
        return "Stopped."
    except Exception as e:
        return f"Stop failed: {e}"

@server.tool(name="r2d2_drive", description="Drive with an index 0–61 (same mapping as the browser slider). 31 = stop, >31 forward, <31 reverse.")
async def tool_drive(index: int) -> str:
    if not 0 <= index <= 61:
        return "Error: index must be 0–61."
    try:
        await SESSION.write_hex(DRIVE_CONTROLS[index])
        return f"Drove with index {index}."
    except Exception as e:
        return f"Drive failed: {e}"

@server.tool(name="r2d2_turn", description="Turn with an index 0–32 (hard-left to hard-right). 17 is straight.")
async def tool_turn(index: int) -> str:
    if not 0 <= index <= 32:
        return "Error: index must be 0–32."
    try:
        await SESSION.write_hex(TURN_SIGNALS[index])
        return f"Turned with index {index}."
    except Exception as e:
        return f"Turn failed: {e}"

@server.tool(name="r2d2_play_sound", description=f"Play a named R2D2 sound. Available: {', '.join(sorted(SOUNDS.keys()))}")
async def tool_play(name: str) -> str:
    if name not in SOUNDS:
        return f"Unknown sound: {name}. Available: {', '.join(sorted(SOUNDS.keys()))}"
    try:
        await SESSION.write_hex(SOUNDS[name])
        return f"Played sound: {name}."
    except Exception as e:
        return f"Sound failed: {e}"

@server.tool(name="r2d2_status", description="Return BLE connection status and device address.")
async def tool_status() -> str:
    connected = bool(SESSION.client and SESSION.client.is_connected)
    return f"connected={connected}, address={SESSION.device_address}"

@server.tool(name="r2d2_disconnect", description="Disconnect from the robot.")
async def tool_disconnect() -> str:
    try:
        await SESSION.disconnect()
        return "Disconnected."
    except Exception as e:
        return f"Disconnect failed: {e}"

if __name__ == "__main__":
    asyncio.run(server.run_stdio_async())
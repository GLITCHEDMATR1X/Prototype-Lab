AFTERLIFE OF IO — SABLE MACHINE PIECES — PASS 119

The runtime discovers every PNG directly from this folder. Replace PNGs in place
or add new PNGs here; catalog.json supplies optional behavior/price metadata.

BUILT-IN PART ROLES

  CORE HOUSING
    Power source. A valid drive requires the same Core Housing to touch both the
    Gear Cluster and Pivot Ring.

  GEAR CLUSTER
    Drive intermediary. Must touch the Core Housing and Pivot Ring. Powered Gear
    Clusters shake subtly; the Pivot Ring is the visible rotating gear above it.

  PIVOT RING
    Powered rotational anchor. Requires Core + Gear contact. A powered Pivot can
    drive attached Rotor Fans and Conduit Pipes.

  ROTOR FAN
    If touching a powered Pivot Ring, the fan rotates around its own center. Its
    world position remains fixed.

  CONDUIT PIPE
    A true left/right two-ended link. Drop either endpoint onto a powered
    Pivot/Gear surface and that exact endpoint becomes the hinge. The opposite
    end hangs under a damped gravity response while the Pivot carries the hinge
    around. Touch the free endpoint to a separate Core/Gear/Pivot/Frame/Cosmetic
    component to form a second persistent hinge. The Pipe is always a fixed-size
    rigid rod: it never stretches, squashes, or reshapes. Crank motion transfers
    through the rod as positional tension to the attached movable component.

  FRAME PLATE
    Cosmetic overlay. It does not transmit power and always renders above other
    machine pieces when they overlap.

CONTACT RULE

A Pivot Ring becomes powered only when all three physical contacts are true in
the same era and walk layer:

    CORE <-> GEAR
    CORE <-> PIVOT
    GEAR <-> PIVOT

This keeps power readable and prevents a remote Gear or Pivot from operating.

CATALOG.JSON

Optional fields per PNG stem:
  name          display name in Sable's catalogue
  cost          Bits charged when Sable sells one inventory piece
  world_height  logical world presentation height
  role          core | gear | pivot | fan | pipe | frame | cosmetic
  touch_radius  world-unit contact radius
  spin_dps      degrees per second for powered rotating pieces
  description   compact catalogue help line

Unlisted PNGs still appear automatically using safe cosmetic defaults.

Pass 119 uses fixed-length position constraints for Conduit Pipes. A single pin
acts as a damped gravity hinge; a second pin remains attached and transfers crank
motion into the connected movable component instead of deforming the Pipe art.


PASS 104 INVENTORY / HOTBAR
Sable purchases add one part to IO's inventory. Up to nine live catalogue parts are shown in a compact bottom-center hotbar. Press the displayed number key to place one owned part near IO. Hold LMB on any placed component to move it directly. The developer console (` or F10) supports `give all` for testing. The runtime continues reading the exact PNGs in this folder directly.


PASS 112 DIRECT MANIPULATION
- Hold LMB: move an unlocked placed part.
- Hold CTRL + LMB and drag left/right: rotate that part; angle persists in saves.
- RMB: return an unlocked placed part to IO's machine inventory.
- The permanent Core cannot be moved, flipped, or reclaimed.

The machine audio replacement stem is assets/audio/sfx/machine_loop.*.


PASS 119 RIGID PIPE HINGES
- LEFT and RIGHT are persistent semantic endpoints, independent of sprite rotation.
- A Pivot/Gear endpoint contact creates a saved first hinge; it does not auto-disconnect.
- A one-ended Pipe is a fixed-length pendulum around that pin.
- The free endpoint can create a second persistent hinge on an unlocked compatible part.
- A two-ended Pipe remains exactly its authored size and transfers constraint tension into the attached part.
- No runtime Pipe stretching, compression, telescoping, or texture reshaping is allowed.
- The locked permanent Core is simply a fixed Core Housing in the machine graph; no special time/circuit completion rule applies.
- Dragging the Pipe intentionally clears its joints so it can be rebuilt elsewhere.


PASS 121 GENERIC MACHINE POWER
- The old Time Stabilizer concept is removed from machine gameplay.
- The fixed world Core remains as a permanent Core Housing / machine anchor.
- A valid touching Core + Gear + Pivot triangle powers immediately through the normal machine graph.
- Pipes/fans inherit power from their normal powered attachments; no Pipe-to-Core loop closure is required.
- No extra ONLINE/OFFLINE status label is drawn above the Core or above the hotbar.
- Ctrl+LMB flips unlocked parts horizontally; RMB reclaims them.
- Machine properties/upgrades can be layered onto the powered state later without changing the base generator rule.

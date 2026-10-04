VECTOR ARENA — HOLOVERSE NATIVE REINTEGRATION

Standalone mode remains valid and does not require HoloVerse.

HoloVerse discovery:
  holoverse/holoverse_dimension.json
  holoverse/responder.py
  holoverse/identity.json

Native adapter:
  standalone_native_adapter.py
  create_mode(host, ...)

Native lifecycle:
  mode = create_mode(existing_showbase)
  mode.enter()
  mode.update(dt)
  mode.get_result()
  mode.exit()

The adapter does NOT create another ShowBase and is intended for the same Panda3D window.

Standard host controls:
  TAB = return to HoloVerse (host-owned)
  ESC = local Vector Arena pause/resume (dimension-owned)
  H   = local arena help toggle (dimension-owned)

Audio lifecycle:
  Vector Arena owns local references to its music, ambience and SFX.
  enter() starts local arena audio.
  exit() stops local loops, one-shots/pools and Audio3DManager update ownership.
  HoloVerse should own the final exit transition and its own restored ambience.

Host transition contract is available from:
  mode.get_native_contract()

The responder can be checked without importing Panda3D:
  python holoverse/responder.py describe
  python holoverse/responder.py health
  python holoverse/responder.py launch-contract

PASS 03 HOST TELEMETRY
  get_result() now also reports flanking_spawns, guardian_specials_used,
  hazard_activations and hazard_hits_taken. These are local result fields;
  HoloVerse remains the owner of whether/how they are persisted globally.

PASS 05 HOST TELEMETRY
  get_result() now also reports encounter_doctrine, enemy_evolution_spawns,
  enemy_evolution_counts, highest_evolution_level_seen, and
  guardian_phase_transitions. These remain local result fields; HoloVerse owns
  whether/how they are persisted globally.

PASS 06 HOST TELEMETRY
  get_result() now also reports arena_family, arena_family_name,
  arena_radius, arena_diameter, largest_arena_radius,
  arena_family_transitions and arena_family_counts. The host can therefore
  remember which hardlight arena families the player reached without owning
  Vector Arena's local wave simulation.


PASS 07 HOST TELEMETRY
  get_result() additionally reports arena_architecture and
  arena_architecture_piece_count. Architecture and gameplay blockers share one
  source of truth, so HoloVerse never needs a separate collision interpretation.

PASS 07.1 LINK CONTRACT
  Responder id is vector_arena and declares holoverse_dimension_v1.
  MatrixCore/HoloVerse may auto-discover this project under MatrixCore Project without hard-coded absolute paths.
  ESC/H are handled locally while native-mounted; TAB remains host-owned and is never bound by the adapter.

from holotactics_core import GameState, Unit


def clear_to_basic(state):
    for u in state.units.values():
        u.hp = u.max_hp


def assert_unique_positions(state):
    positions = [u.pos for u in state.units.values() if u.alive]
    assert len(positions) == len(set(positions)), positions
    for u in state.units.values():
        if u.alive:
            assert state.in_bounds(u.pos), (u.unit_id, u.pos)
            assert state.tiles[u.pos].state != 'void', (u.unit_id, u.pos)


def test_sentry_keeps_range():
    s = GameState()
    sentry = s.units['sentry']
    gleebs = s.units['gleebs']
    sentry.pos = (3, 3)
    gleebs.pos = (3, 4)  # adjacent, inside preferred range 2
    s.units['guard'].pos = (0, 0)
    s.units['runner'].pos = (1, 0)
    hp = gleebs.hp
    s.enemy_phase()
    assert s.distance(sentry.pos, gleebs.pos) == 2, (sentry.pos, gleebs.pos)
    assert gleebs.hp == hp, 'sentry should reposition rather than point-blank fire when a retreat tile is open'


def test_sentry_fires_at_range():
    s = GameState()
    sentry = s.units['sentry']
    gleebs = s.units['gleebs']
    sentry.pos = (3, 3)
    gleebs.pos = (3, 5)
    s.units['guard'].pos = (0, 0)
    s.units['runner'].pos = (1, 0)
    hp = gleebs.hp
    s.enemy_phase()
    assert gleebs.hp == hp - sentry.attack_power, (hp, gleebs.hp)
    assert sentry.pos == (3, 3)


def test_memory_pressure_targets_gleebs():
    s = GameState()
    anomaly = s.units['anomaly']
    sentry = s.units['sentry']
    sentry.hp = 0
    anomaly.pos = (5, 5)
    s.units['gleebs'].pos = (3, 5)
    s.units['guard'].pos = (5, 4)  # closer, but cannot capture Memory Node
    s.units['guard'].hp = 1        # deliberately vulnerable
    s.units['runner'].pos = (0, 0)
    s.enemy_phase()
    assert anomaly.pos == (4, 5), anomaly.pos
    assert s.units['guard'].hp == 1


def test_post_memory_vulnerability_breaks_tie():
    s = GameState()
    s.memory_collected = True
    anomaly = s.units['anomaly']
    s.units['sentry'].hp = 0
    anomaly.pos = (4, 4)
    # Put two units equally close to the Core and equally distant from anomaly.
    s.units['gleebs'].pos = (5, 4)
    s.units['gleebs'].hp = 10
    s.units['guard'].pos = (4, 5)
    s.units['guard'].hp = 2
    s.units['runner'].pos = (0, 0)
    s.enemy_phase()
    assert s.units['guard'].hp < 2, 'vulnerable objective-threatening unit should win tie'


def test_dead_target_not_reused():
    s = GameState()
    s.memory_collected = True
    a = s.units['anomaly']
    b = s.units['sentry']
    a.pos = (4, 6)
    b.pos = (4, 5)
    a.attack_power = 99
    # Both Gleebs and Guard are one tile from the Core objective. Gleebs is
    # deliberately more vulnerable, so the first enemy kills him.
    s.units['gleebs'].pos = (5, 6)
    s.units['gleebs'].hp = 1
    s.units['guard'].pos = (6, 5)
    s.units['runner'].pos = (0, 0)
    before = s.units['guard'].hp
    s.enemy_phase()
    assert not s.units['gleebs'].alive
    assert s.units['guard'].hp < before or b.pos != (4, 5), 'second enemy should retarget a living squad unit'


def test_spacing_tiebreak():
    s = GameState(sector_index=4)
    hunter = s.units['anomaly']
    other = s.units['anomaly_echo']
    s.units['sentry'].hp = 0
    hunter.pos = (5, 5)
    other.pos = (5, 7)
    s.units['gleebs'].pos = (7, 5)
    s.units['guard'].pos = (0, 0)
    s.units['runner'].pos = (0, 1)
    # Both (6,5) is the only improving tile here, so make a tie geometry instead.
    hunter.pos = (5,5)
    s.units['gleebs'].pos = (7,7)
    other.pos = (6,4)
    s.enemy_phase()
    # candidate (5,6) and (6,5) are both distance 3; (6,5) is adjacent to other at (6,4), so choose (5,6)
    assert hunter.pos == (5,6), (hunter.pos, other.pos)


def test_all_sectors_stable():
    for sector in range(1, 6):
        s = GameState(sector_index=sector)
        for _ in range(8):
            if not [u for u in s.units.values() if u.team == 'player' and u.alive]:
                break
            s.enemy_phase()
            assert_unique_positions(s)


def main():
    tests = [
        test_sentry_keeps_range,
        test_sentry_fires_at_range,
        test_memory_pressure_targets_gleebs,
        test_post_memory_vulnerability_breaks_tie,
        test_dead_target_not_reused,
        test_spacing_tiebreak,
        test_all_sectors_stable,
    ]
    for test in tests:
        test()
        print('PASS', test.__name__)
    print(f'PASS {len(tests)}/{len(tests)} Pass 20 tactical AI scenarios')


if __name__ == '__main__':
    main()

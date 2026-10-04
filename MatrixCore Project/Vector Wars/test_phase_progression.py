from phase_progression import PhaseProgression, WarPhase

p = PhaseProgression()
assert p.active_phase is WarPhase.GROUND
assert p.active_mode == 1
assert p.advance_ground_to_air() is True
assert p.active_phase is WarPhase.AIR
assert p.active_mode == 0
assert p.ground_transition_count == 1
assert p.advance_ground_to_air() is False
assert p.ground_transition_count == 1
assert p.advance_air_to_ocean() is True
assert p.active_phase is WarPhase.OCEAN
assert p.active_mode == 2
assert p.air_transition_count == 1
assert p.advance_air_to_ocean() is False
assert p.air_transition_count == 1
assert p.campaign_complete is False
assert p.complete_ocean_campaign() is True
assert p.campaign_complete is True
assert p.campaign_completion_count == 1
assert p.complete_ocean_campaign() is False
assert p.campaign_completion_count == 1
print('phase progression: PASS')

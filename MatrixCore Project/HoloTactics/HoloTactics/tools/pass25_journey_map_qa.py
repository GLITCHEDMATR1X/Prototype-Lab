from holotactics_core import GameState, SECTOR_NAMES, create_game_for_sector


def route_states(state):
    result=[]
    for index in range(1,6):
        name=SECTOR_NAMES[index]
        if index < state.sector_index or name in state.cleared_sectors:
            result.append('SEALED')
        elif index == state.sector_index:
            result.append('SEALED' if state.victory() else 'CURRENT')
        else:
            result.append('LOCKED')
    return result

checks=[]
def check(name, cond):
    assert cond, name
    checks.append(name)

s1=create_game_for_sector(1)
check('sector1 route', route_states(s1)==['CURRENT','LOCKED','LOCKED','LOCKED','LOCKED'])
s2=create_game_for_sector(2,[SECTOR_NAMES[1]])
check('sector2 route', route_states(s2)==['SEALED','CURRENT','LOCKED','LOCKED','LOCKED'])
s3=create_game_for_sector(3,[SECTOR_NAMES[1],SECTOR_NAMES[2]])
check('sector3 route', route_states(s3)==['SEALED','SEALED','CURRENT','LOCKED','LOCKED'])
s4=create_game_for_sector(4,[SECTOR_NAMES[1],SECTOR_NAMES[2],SECTOR_NAMES[3]])
check('sector4 route', route_states(s4)==['SEALED','SEALED','SEALED','CURRENT','LOCKED'])
s5=create_game_for_sector(5,[SECTOR_NAMES[1],SECTOR_NAMES[2],SECTOR_NAMES[3],SECTOR_NAMES[4]])
check('sector5 route', route_states(s5)==['SEALED','SEALED','SEALED','SEALED','CURRENT'])
# Victory marks current as sealed, but does not silently unlock/advance the next sector.
s3.memory_collected=True
s3.core_destroyed=True
s3.extraction_reached=True
check('sealed current after victory', route_states(s3)==['SEALED','SEALED','SEALED','LOCKED','LOCKED'])
# Route display must be observational: generating equivalent state lists cannot mutate snapshot data.
snap=s4.snapshot()
_ = route_states(s4)
check('route inspection is read only', s4.snapshot()==snap)
# Existing distinct objective identities remain present.
check('sector2 relays intact', create_game_for_sector(2).nodes['memory'].name=='Signal Relay Alpha')
check('sector3 fracture identity intact', 'Fracture' in create_game_for_sector(3).nodes['die'].name)
check('sector4 uplink identity intact', 'Uplink' in create_game_for_sector(4).nodes['patch'].name)
check('sector5 horizon identity intact', 'Horizon' in create_game_for_sector(5).nodes['patch'].name)
print(f'Pass 25 Journey Map QA: {len(checks)}/{len(checks)} PASS')
for name in checks:
    print('PASS', name)

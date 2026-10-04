#!/usr/bin/env python3
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from combat_outcomes import CombatOutcomeAuthority, CombatPhaseStatus
from ground_operation import GroundOperation, GroundOperationStage
from air_operation import AirOperation
from ocean_operation import OceanOperation
from phase_progression import PhaseProgression, WarPhase
from campaign_save import load_campaign_save, write_campaign_save, clear_campaign_save, restore_campaign_save


def authorities():
    return PhaseProgression(), GroundOperation(), AirOperation(), OceanOperation(), CombatOutcomeAuthority()


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / 'campaign_save.json'
        pp, g, a, o, co = authorities()
        g.street_destroyed = 8
        g.giants_destroyed = 1
        g.stage = GroundOperationStage.COMPLETE
        g.completed_operations = 1
        a.fighter_kills = 3
        pp.active_phase = WarPhase.AIR
        pp.ground_transition_count = 1
        write_campaign_save(path, pp, g, a, o)
        assert path.is_file(), 'save not written'
        assert not path.with_suffix('.json.tmp').exists(), 'temp file leaked'

        raw = load_campaign_save(path)
        assert raw and raw['phase'] == 'AIR', raw
        pp2, g2, a2, o2, co2 = authorities()
        assert restore_campaign_save(raw, pp2, g2, a2, o2, co2)
        assert pp2.active_phase is WarPhase.AIR
        assert g2.complete
        assert a2.fighter_kills == 3 and a2.ufo_kills == 0
        assert co2.status['GROUND'] is CombatPhaseStatus.COMPLETE
        assert co2.status['AIR'] is CombatPhaseStatus.ACTIVE

        # Later-phase saves must restore earlier completed phase invariants.
        path.write_text('{"schema":1,"phase":"OCEAN","campaign_complete":false,"ground":{},"air":{},"ocean":{"warship_kills":2}}', encoding='utf-8')
        raw = load_campaign_save(path)
        pp3, g3, a3, o3, co3 = authorities()
        assert restore_campaign_save(raw, pp3, g3, a3, o3, co3)
        assert pp3.active_phase is WarPhase.OCEAN
        assert g3.complete and a3.complete
        assert o3.warship_kills == 2 and not o3.complete

        # Corrupt/incompatible data never blocks a new campaign.
        path.write_text('{broken', encoding='utf-8')
        assert load_campaign_save(path) is None
        path.write_text('{"schema":999,"phase":"AIR"}', encoding='utf-8')
        assert load_campaign_save(path) is None

        clear_campaign_save(path)
        assert not path.exists()

    print('campaign_save: PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

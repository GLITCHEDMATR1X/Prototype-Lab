"""Developer-only, opt-in process-chain QA. Never enabled by a normal launcher.

Enabled with GX_TRAVEL_QA=1 and GX_TRAVEL_QA_PLAN=<plan.json>. Each process runs one
plan step, records what it saw to events.jsonl, then performs the step's action.

Actions
  dreamcatcher  Limbo: open the TV menu and press DREAMCATCHER
  nightmare     DreamCatcher: mark house progress, tune CH07 DREAM and press T
  complete      Andrew: finish the instance for real, then press Q (no pause needed)
  back          any world: use the normal return path
  finale        DreamCatcher: check restored house, finish the attic finale, press Esc
  done          Limbo: check recorded completions and exit
"""
import json
import os
from pathlib import Path
import time

from panda3d.core import Point3, Vec3, Filename

from gx_common import shared


def attach(travel):
    path = Path(os.environ['GX_TRAVEL_QA_PLAN'])
    started = time.monotonic()

    def drive(task):
        if travel.busy or time.monotonic() - started < .6:
            return task.cont
        plan = json.loads(path.read_text())
        step = plan['steps'][plan['index']]
        assert step['world'] == travel.world_id, (step, travel.world_id)
        game = travel.base
        output = Path(plan['output'])
        output.mkdir(parents=True, exist_ok=True)
        action = step['action']
        record = {'index': plan['index'], 'world': travel.world_id, 'pid': os.getpid(),
                  'root': str(travel.root), 'back_stack': travel.stack, 'action': action,
                  'arrived_from': travel.arrived_from}
        if travel.world_id == 'mirrors_limbo':
            if getattr(game, 'boot_splash_root', None):
                game.boot_splash_root.removeNode(); game.boot_splash_root = None
            if not plan['index']:
                assert not game.tv_discovered, 'Fresh player must not see the TV early'
                game._discover_tv_on_return('house_return')
            assert game.tv_discovered
            game.ensure_start_anomaly_tv()
            center = Point3(game.world_semantic_anchors['start_anomaly_tv']['center'])
            game.camera.setPos(center.x, center.y - 3.4, game.eye_height)
            game.camera.lookAt(Point3(center.x, center.y, 1.0))
            game.heading = game.camera.getH(); game.pitch = game.camera.getP()
            game.messenger.send('e')
            assert game.tv_channel_menu is not None
            record['buttons'] = [game.tv_framework_button['text'], game.tv_dreamcatcher_button['text']]
            record['linked_status'] = game.tv_channel_status['text']
            record['settings'] = dict(game.game_settings)
            if action == 'done':
                progress = shared.load_progress()
                assert progress['dreamcatcher']['completed'], 'DreamCatcher completion was not recorded'
                assert progress['andrews_nightmare']['completed'], "Andrew's completion was not recorded"
                assert progress['dreamcatcher_house'] is None, 'Finished house must start fresh next visit'
                assert 'HOUSE CLEARED' in record['linked_status'], record['linked_status']
                record['progress'] = progress
        elif travel.world_id == 'dreamcatcher_alternate':
            record['display'] = dict(game.display_settings)
            record['mouse_sens'] = game.mouse_sens
            record['fov'] = round(float(game.camLens.getHfov()), 2)
            game._window_was_foreground = True
            if action == 'nightmare':
                # House progress the player made before visiting Andrew.
                game.tv_task.update({'state': 'completed', 'completion_count': 1})
                game.tv_task_02.update({'state': 'changed', 'frame_straightened': True})
                game._set_task_frame_crooked(False)
                game.player = Vec3(3.55, 1.35, game.floor_z)
                game.heading = -90.; game.pitch = -8.; game._apply_camera()
                game._interact()
                assert game.tv_focused
                while game.tv_channel != 7:
                    game.messenger.send('arrow_right')
                assert game._dream_link_indicator_active()
                game._render_tv_frame(force=True)
                game._update_prompt()
                # Sitting at the TV already acknowledged task 02; remember the exact house state.
                plan['expect_house'] = {k: dict(getattr(game, k)) for k in ('tv_task', 'tv_task_02', 'tv_task_03')}
                plan['expect_broadcast'] = [game.task_broadcast_mode, game.task_broadcast_channel]
            elif action == 'finale':
                assert travel.arrived_from == 'andrews_nightmare', travel.arrived_from
                for key, expected in plan['expect_house'].items():
                    assert dict(getattr(game, key)) == expected, (key, getattr(game, key), expected)
                assert [game.task_broadcast_mode, game.task_broadcast_channel] == plan['expect_broadcast']
                assert abs(game.task_frame_root.getR()) < 1e-3, 'Straightened frame was not restored'
                record['restored_house'] = plan['expect_house']
                game.finale_finished = True
                game._on_house_complete()
                assert shared.load_progress()['dreamcatcher']['completed']
            else:
                game.messenger.send('escape')
                assert not game.travel_back_button.isHidden()
        else:
            record['settings'] = dict(game.settings)
            if action == 'complete':
                game._finish_instance_collapse()
                game.world.instance_complete = True
                assert shared.load_progress()['andrews_nightmare']['completed']
            else:
                game.messenger.send('escape')
                assert game.paused
        game.graphicsEngine.renderFrame(); game.graphicsEngine.renderFrame()
        assert game.win.saveScreenshot(Filename.fromOsSpecific(str(output / f"stage_{plan['index']}_{travel.world_id}.png")))
        with (output / 'events.jsonl').open('a') as f:
            f.write(json.dumps(record, default=str) + '\n')
        plan['index'] += 1
        path.write_text(json.dumps(plan))
        if action == 'done':
            (output / 'complete.json').write_text(json.dumps({'passed': True, 'last_pid': os.getpid()}))
            game.userExit()
            return task.done
        target = {'dreamcatcher': 'dreamcatcher_alternate', 'nightmare': 'andrews_nightmare',
                  'complete': 'dreamcatcher_alternate', 'finale': 'mirrors_limbo',
                  'back': travel.return_target}[action]
        travel._qa_child_args = list(plan.get('child_args', {}).get(target, []))
        if action == 'dreamcatcher':
            game.tv_dreamcatcher_button['command']()
        elif action == 'nightmare':
            game.messenger.send('t')
        elif action == 'complete':
            game.messenger.send('q')
        elif action == 'finale':
            game.messenger.send('escape')
        elif travel.world_id == 'andrews_nightmare':
            game.messenger.send('q')
        else:
            game.travel_back_button['command']()
        assert travel.process is not None, travel.last_error
        return task.done

    travel.base.taskMgr.add(drive, 'gx-travel-qa-drive', sort=110)

from __future__ import annotations
import ast, json, re, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'verification/reports/pass32_finalization_blockers.json'

def src(rel): return (ROOT/rel).read_text(encoding='utf-8')

def check_audio_source():
    s=src('game/audio.py')
    tree=ast.parse(s)
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='AudioManager')
    fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_effective_music_gain')
    text=ast.get_source_segment(s,fn) or ''
    return {
        'music_gain_independent_of_sfx': 'sfx_volume' not in text and 'MUSIC_TO_SFX_RATIO_CAP' not in text,
        'music_default_075': 'music_volume", 0.75' in text,
        'single_stream_looping': 'pygame.mixer.music.play(loops=-1' in s,
        'stop_before_load': s.find('pygame.mixer.music.stop()') < s.find('pygame.mixer.music.load(str(track))'),
    }

def check_app_source():
    s=src('game/app.py')
    return {
        'mission_pause_menu_state': 'mission_pause_index' in s and 'abort_contract_confirm' in s,
        'escape_opens_pause': 'self._open_mission_pause()' in s and 'self.state = "CONTRACT_BOARD"; self.mission = None; self.paused = False' not in s[s.find('elif event.key == pygame.K_ESCAPE:'):s.find('def update',s.find('elif event.key == pygame.K_ESCAPE:'))],
        'pause_has_resume_settings_abort': all(x in s for x in ['_resume_mission','settings_return_state = "MISSION"','_abort_active_contract']),
        'abort_requires_confirmation': 'if not self.abort_contract_confirm:' in s,
        'settings_mouse_minus_plus': 'settings_minus_rects' in s and 'settings_plus_rects' in s,
        'volume_step_5_percent': 'direction * 0.05' in s,
        'battle_music_kept_in_pause_settings': 'self.settings_return_state == "MISSION"' in s and 'self.audio.set_context("MISSION" if mission_audio_context else self.state' in s,
    }

def check_render_source():
    s=src('game/render.py')
    return {
        'pause_renderer_present': 'def _draw_mission_pause' in s,
        'pause_options_visible': all(x in s for x in ['RESUME CONTRACT','SETTINGS','ABORT CONTRACT','CONFIRM ABORT']),
        'volume_minus_plus_visible': 'self.text(self.canvas, "−"' in s and 'self.text(self.canvas, "+"' in s,
        'old_escape_abort_copy_removed': 'ESC ABORT' not in s,
    }

def check_build_script():
    s=src('platform/windows/BUILD_WINDOWS_FULL_TITLE.bat')
    final_idx=s.find('if exist "%FINALOUT%" rmdir /s /q "%FINALOUT%"')
    build_idx=s.find('PyInstaller')
    tests_idx=s.find('CrashReporterSelfTest=PASS')
    return {
        'staged_build_directory': 'pass32_windows_stage' in s and 'STAGEDIST' in s,
        'final_dist_not_deleted_before_pyinstaller': final_idx > build_idx,
        'final_dist_publish_after_tests': final_idx > s.find('crash-reporter self-test') if 'crash-reporter self-test' in s.lower() else final_idx > s.find('CRASHTEST'),
        'success_marker': 'BUILD_SUCCESS.txt' in s,
        'portable_zip': 'HEX_CONTRACT_Windows_x64.zip' in s,
        'final_exe_verified': 'FINALOUT%\\HEXContractRuntime\\HEXContract.exe' in s,
        'clean_save_guard': 'save_profile.json leaked into the staged runtime' in s,
        'root_wrapper_present': (ROOT/'BUILD_WINDOWS.bat').exists(),
    }

def measure_music():
    out={}
    for path in sorted((ROOT/'assets/music').rglob('*.ogg')):
        proc=subprocess.run(['ffmpeg','-hide_banner','-nostats','-i',str(path),'-filter_complex','ebur128=peak=true','-f','null','-'],capture_output=True,text=True)
        vals=re.findall(r'I:\s*(-?\d+(?:\.\d+)?) LUFS',proc.stderr)
        peaks=re.findall(r'Peak:\s*(-?\d+(?:\.\d+)?) dBFS',proc.stderr)
        out[path.relative_to(ROOT/'assets/music').as_posix()]={
            'integrated_lufs': float(vals[-1]) if vals else None,
            'peak_dbfs': float(peaks[-1]) if peaks else None,
        }
    return out

def runtime_pause_and_settings_test():
    import importlib.util, math, types
    # Reuse the geometry stub from the permanent Pass 29 audit, then extend it
    # with the small event/key surface needed by App.handle_event().
    audit_path = ROOT / "tools" / "pass29_code_audit.py"
    spec = importlib.util.spec_from_file_location("pass29_code_audit_runtime", audit_path)
    audit = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(audit)
    audit.install_pygame_geometry_stub()
    import pygame
    constants = {
        "QUIT": 1, "KEYDOWN": 2, "MOUSEBUTTONDOWN": 3,
        "K_ESCAPE": 27, "K_RETURN": 13, "K_SPACE": 32, "K_UP": 273, "K_DOWN": 274,
        "K_LEFT": 276, "K_RIGHT": 275, "K_w": 119, "K_s": 115, "K_a": 97, "K_d": 100,
        "K_TAB": 9, "K_i": 105, "K_o": 111, "K_r": 114, "K_b": 98, "K_e": 101,
        "K_h": 104, "K_F11": 282, "K_c": 99, "K_n": 110, "K_q": 113, "K_1": 49, "K_2": 50,
    }
    for name, value in constants.items(): setattr(pygame, name, value)
    pygame.event = types.SimpleNamespace(Event=lambda t, **kw: types.SimpleNamespace(type=t, **kw))
    pygame.time = types.SimpleNamespace(get_ticks=lambda: 0)
    # Fresh import after pygame stub is complete.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    for mod in ["game.app"]:
        sys.modules.pop(mod, None)
    from game.app import App

    class Audio:
        def __init__(self): self.played=[]; self.settings=None
        def play(self, key): self.played.append(key)
        def apply_settings(self, settings): self.settings=dict(settings)
    class Renderer:
        def apply_settings(self, settings): self.settings=dict(settings)
    class Crash:
        def breadcrumb(self,*a,**kw): pass
    mission=types.SimpleNamespace(status="ACTIVE", hero_key="nyx", quest_key="purge")
    app=object.__new__(App)
    app.state="MISSION"; app.mission=mission; app.paused=False; app.show_help=False; app.input_mode="keyboard"
    app.audio=Audio(); app.renderer=Renderer(); app.crash_reporter=Crash(); app.running=True
    app.mission_pause_index=0; app.abort_contract_confirm=False; app.selected_hero="nyx"; app.selected_sidekicks=[]
    app.profile={"settings":{"master_volume":0.85,"sfx_volume":0.85,"ambience_volume":0.45,"music_volume":0.75}}
    app.settings_index=3; app.settings_return_state="TITLE"
    app._save_profile=lambda: None; app._checkpoint=lambda reason: None
    app._set_input_mode=lambda mode: setattr(app,"input_mode",mode)
    app._toggle_display_mode=lambda: None
    app._refresh_platform_save_root=lambda: None
    app._platform_toast=lambda *a,**kw: None
    app.controllers={}; app.controller_connected=False
    app.platform_notice=""; app.platform_notice_until=0

    app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    esc_pause = app.state=="MISSION" and app.mission is mission and app.paused is True
    app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN))
    nav_settings = app.mission_pause_index==1
    app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    opens_settings = app.state=="SETTINGS" and app.settings_return_state=="MISSION" and app.paused is True
    app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    returns_paused = app.state=="MISSION" and app.paused is True
    app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    resumes = app.state=="MISSION" and app.paused is False and app.mission is mission

    # 100% music must remain independent of SFX and settings changes must move both directions.
    app.state="SETTINGS"; app.settings_return_state="TITLE"; app.settings_index=3
    app.profile["settings"]["music_volume"]=0.75
    app._adjust_setting(1); up=app.profile["settings"]["music_volume"]
    app._adjust_setting(-1); down=app.profile["settings"]["music_volume"]
    volume_moves = abs(up-0.80)<1e-9 and abs(down-0.75)<1e-9 and app.audio.settings is not None

    # Abort is intentionally two-step.
    app.state="MISSION"; app.mission=mission; app.paused=True; app.mission_pause_index=2; app.abort_contract_confirm=False
    app._activate_mission_pause_option()
    first_abort_safe = app.mission is mission and app.abort_contract_confirm is True
    app._activate_mission_pause_option()
    second_abort_exits = app.mission is None and app.state=="CONTRACT_BOARD"
    return {
        "esc_opens_pause_without_destroying_mission": esc_pause,
        "pause_navigation_reaches_settings": nav_settings,
        "settings_open_from_pause": opens_settings,
        "settings_return_keeps_mission_paused": returns_paused,
        "escape_from_pause_resumes": resumes,
        "volume_adjusts_up_and_down_and_applies": volume_moves,
        "abort_requires_first_confirmation": first_abort_safe,
        "confirmed_abort_returns_board": second_abort_exits,
    }

def main():
    music=measure_music()
    checks={}
    for group in (check_audio_source(),check_app_source(),check_render_source(),check_build_script(),runtime_pause_and_settings_test()): checks.update(group)
    checks['five_music_tracks']=len(music)==5
    checks['music_loudness_about_minus16']=all(v['integrated_lufs'] is not None and -16.3 <= v['integrated_lufs'] <= -15.7 for v in music.values())
    manifest=json.loads((ROOT/'assets/music/music_manifest.json').read_text())
    checks['manifest_independent_music']=manifest.get('mix',{}).get('independent_music_slider') is True
    payload={'pass32_finalization_blockers':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'music_measurements':music}
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps(payload,indent=2)+'\n')
    print(json.dumps(payload,indent=2))
    return 0 if all(checks.values()) else 1
if __name__=='__main__': raise SystemExit(main())

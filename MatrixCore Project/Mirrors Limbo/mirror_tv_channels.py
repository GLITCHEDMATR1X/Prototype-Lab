"""Roadside TV channel menu: FRAMEWORK (in-world) and DREAMCATCHER (linked world)."""
from direct.gui.DirectGui import DirectFrame, DirectButton, DirectLabel
from direct.gui import DirectGuiGlobals as DGG
from panda3d.core import Vec3

from gx_common import shared
from gx_common.travel import WorldTravel

HOLOVERSE_BLOCKED = 'DREAMCATCHER OPENS FROM STANDALONE MIRROR\'S LIMBO'


def install(game, root):
    game.tv_channel_menu = None
    game.tv_channel_status = None
    game.world_travel = None
    if game._holoverse_embedded:
        # Travel replaces the whole process. Inside HoloVerse that would close the host,
        # so the linked worlds are only offered from the standalone game.
        return

    def before_leave():
        game.save_game_settings()
        game.save_runtime_checkpoint(force=True)
        for key in game.keys:
            game.keys[key] = False

    def error(message):
        if game.tv_channel_status:
            game.tv_channel_status['text'] = ('DREAMCATCHER IS MISSING FROM THIS INSTALL'
                if 'missing' in message.lower() else 'COULD NOT OPEN DREAMCATCHER — LIMBO RESTORED')
        game.pause_menu_open = game.tv_channel_menu is not None
        game.set_cursor_for_editor(game.tv_channel_menu is not None)

    def activate():
        game.pause_menu_open = False
        if game.pause_menu_root:
            game.pause_menu_root.hide()
        for key in game.keys:
            game.keys[key] = False
        game.set_cursor_for_editor(False)

    game.world_travel = WorldTravel(game, root, 'mirrors_limbo',
        before_leave=before_leave, on_error=error, activate=activate, retire=game.userExit)
    game.world_travel.start_receiving()


def _travel_busy(game):
    return game.world_travel is not None and game.world_travel.busy


def close(game):
    if _travel_busy(game):
        return
    if game.tv_channel_menu is not None:
        game.tv_channel_menu.destroy()
        game.tv_channel_menu = None
        game.tv_channel_status = None
        game.pause_menu_open = False
        for key in game.keys:
            game.keys[key] = False
        game.set_cursor_for_editor(False)


def linked_status_text():
    """One quiet line naming what the player has already finished in the linked worlds."""
    progress = shared.load_progress()
    parts = []
    if progress['dreamcatcher'].get('completed'):
        parts.append('HOUSE CLEARED')
    if progress['andrews_nightmare'].get('completed'):
        endings = progress['andrews_nightmare'].get('endings') or []
        parts.append('NIGHTMARE DISCONNECTED' if 'null_disconnect' in endings else 'NIGHTMARE BROKEN')
    return '  //  '.join(parts)


def open_channels(game):
    if game.tv_channel_menu is not None or _travel_busy(game):
        return True
    game.clear_attendant_speech()
    game._set_glitch_context_prompt(None)
    game.pause_menu_open = True
    game.planar_velocity = Vec3(0, 0, 0)
    for key in game.keys:
        game.keys[key] = False
    game.set_cursor_for_editor(True)
    root = DirectFrame(parent=game.aspect2d, frameColor=(.012,.018,.020,.97),
                       frameSize=(-.66,.66,-.27,.27), relief=DGG.FLAT)
    game.tv_channel_menu = root
    DirectLabel(parent=root, text='TV CHANNELS', text_scale=.052,
                pos=(0,0,.16), frameColor=(0,0,0,0), text_fg=(.82,.89,.87,1))

    def framework():
        close(game)
        game.enter_framework_from_tv()

    def dreamcatcher():
        if game.world_travel is None:
            game.tv_channel_status['text'] = HOLOVERSE_BLOCKED
            return
        game.world_travel.go('dreamcatcher_alternate')

    game.tv_framework_button = DirectButton(parent=root, text='FRAMEWORK', text_scale=.039,
        pos=(-.32,0,.015), frameSize=(-.275,.275,-.065,.065), relief=DGG.FLAT,
        frameColor=(.06,.08,.075,1), text_fg=(.87,.90,.83,1), command=framework)
    game.tv_dreamcatcher_button = DirectButton(parent=root, text='DREAMCATCHER', text_scale=.039,
        pos=(.32,0,.015), frameSize=(-.275,.275,-.065,.065), relief=DGG.FLAT,
        frameColor=(.045,.09,.095,1), text_fg=(.66,.87,.87,1), command=dreamcatcher)
    status = HOLOVERSE_BLOCKED if game.world_travel is None else linked_status_text()
    game.tv_channel_status = DirectLabel(parent=root, text=status, text_scale=.021,
        pos=(0,0,-.10), frameColor=(0,0,0,0), text_fg=(.78,.72,.62,1))
    DirectButton(parent=root, text='BACK', text_scale=.031, pos=(0,0,-.19),
        frameSize=(-.12,.12,-.038,.038), relief=DGG.FLAT, frameColor=(.04,.05,.05,1),
        text_fg=(.72,.76,.75,1), command=lambda: close(game))
    return True

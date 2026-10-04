from __future__ import annotations

import pygame

# Named actions keep controls inspectable and ready for a future rebinding layer.
ACTIONS = {
    "move_left": (pygame.K_a, pygame.K_LEFT),
    "move_right": (pygame.K_d, pygame.K_RIGHT),
    "move_up": (pygame.K_w, pygame.K_UP),
    "move_down": (pygame.K_s, pygame.K_DOWN),
    "confirm": (pygame.K_RETURN, pygame.K_SPACE, pygame.K_e),
    "back": (pygame.K_ESCAPE,),
    "help": (pygame.K_F1, pygame.K_h),
    "settings": (pygame.K_F2,),
    "memory_archive": (pygame.K_m,),
    "fullscreen": (pygame.K_F11,),
    "camera_1": (pygame.K_1,),
    "camera_2": (pygame.K_2,),
    "camera_3": (pygame.K_3,),
    "camera_4": (pygame.K_TAB,),
    "method_1": (pygame.K_4,),
    "method_2": (pygame.K_5,),
    "method_3": (pygame.K_6,),
    "method_4": (pygame.K_7,),
    "method_5": (pygame.K_8,),
}


def pressed(keys: pygame.key.ScancodeWrapper, action: str) -> bool:
    return any(keys[key] for key in ACTIONS[action])

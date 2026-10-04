from __future__ import annotations

from typing import Any

HEROES: dict[str, dict[str, Any]] = {
    "nyx": {
        "name": "NYX-7",
        "title": "HEX BLADE",
        "color": (49, 225, 255),
        "accent": (196, 64, 255),
        "max_hp": 122,
        "speed": 236.0,
        "damage": 24.0,
        "range": 78.0,
        "attack_cooldown": 0.42,
        "strength": "Aggressive pursuit / isolated targets",
        "weakness": "Overcommits when enemies are wounded",
        "ability": "SHADOW SKIP",
        "weapon": "Mono-katana + curse pistol",
        "discipline": 0.48,
        "caution": 0.35,
        "tech": 0.30,
        "arcana": 0.82,
        "aggression": 0.98,
        "altruism": 0.24,
        "resolve": 0.88,
        "curiosity": 0.58,
        "protectiveness": 0.31,
        "personality": ["RELENTLESS", "OPPORTUNISTIC", "IMPULSIVE"],
        "doctrine": "Finishes wounded targets even when the contract points elsewhere.",
        "origin": "LOWER NEON WARD / FAILED HEX PROGRAM",
        "body": "Lean synthetic frame wrapped in a split shadow-cloak",
        "armor": "Reactive duskweave / exposed phase joints",
        "visual_signature": "Hooded cyan visor, violet cloak tails, mono-katana spine",
        "ability_detail": "Phase-jumps behind a damaged hostile and commits to a finishing strike.",
        "weapon_detail": "Close mono-katana; compact curse pistol for route pressure.",
        "height": "1.74 m",
        "actor_scale": 1.12,
        "recovery_affinity": 0.72,
        "guild_epithet": "THE KNIFE BETWEEN SIGNALS",
        "field_quote": "Point me at the part that still thinks it can run.",
        "crest": "BROKEN CRESCENT",
    },
    "circuit": {
        "name": "BROTHER CIRCUIT",
        "title": "SANCTIFIED MACHINE",
        "color": (255, 205, 76),
        "accent": (88, 224, 255),
        "max_hp": 176,
        "speed": 156.0,
        "damage": 28.0,
        "range": 112.0,
        "attack_cooldown": 0.66,
        "strength": "Durable / disciplined / anti-corruption",
        "weakness": "Slow pursuit and route recovery",
        "ability": "SANCTUARY PROTOCOL",
        "weapon": "Arc hammer + prayer drone",
        "discipline": 0.94,
        "caution": 0.72,
        "tech": 0.52,
        "arcana": 0.88,
        "aggression": 0.58,
        "altruism": 0.92,
        "resolve": 0.96,
        "curiosity": 0.26,
        "protectiveness": 0.99,
        "personality": ["PROTECTIVE", "DISCIPLINED", "STEADFAST"],
        "doctrine": "Intercepts threats near civilians before pursuing the shortest route.",
        "origin": "ORDER OF THE LAST CIRCUIT / MOBILE CHAPEL 12",
        "body": "Broad sanctified chassis with layered reliquary plating",
        "armor": "Consecrated plate / floating prayer-drone ward",
        "visual_signature": "Gold armor blocks, cyan halo, oversized arc hammer",
        "ability_detail": "Projects a sanctuary shell that suppresses incoming damage around his frame.",
        "weapon_detail": "Two-handed arc hammer supported by an orbiting prayer drone.",
        "height": "2.08 m",
        "actor_scale": 1.28,
        "recovery_affinity": 0.90,
        "guild_epithet": "THE LAST MOVING CHAPEL",
        "field_quote": "Stand behind me. I have already counted the cost.",
        "crest": "HALOED CIRCUIT",
    },
    "vesper": {
        "name": "VESPER COIL",
        "title": "GHOST OPERATIVE",
        "color": (124, 255, 154),
        "accent": (234, 83, 255),
        "max_hp": 92,
        "speed": 202.0,
        "damage": 15.8,
        "range": 350.0,
        "attack_cooldown": 0.58,
        "strength": "Hacking / trap detection / ranged control",
        "weakness": "Fragile under direct pressure",
        "ability": "GHOST OVERRIDE",
        "weapon": "Smartbow + data dagger",
        "discipline": 0.82,
        "caution": 0.86,
        "tech": 0.98,
        "arcana": 0.55,
        "aggression": 0.34,
        "altruism": 0.67,
        "resolve": 0.64,
        "curiosity": 0.93,
        "protectiveness": 0.55,
        "personality": ["METHODICAL", "CURIOUS", "SELF-PRESERVING"],
        "doctrine": "Avoids crowded fights and exploits machines to reach objectives safely.",
        "origin": "BLACKGLASS INTELLIGENCE CELL / STATUS ERASED",
        "body": "Light infiltrator rig under a translucent signal mantle",
        "armor": "Low-profile ghostmesh / no heavy plate",
        "visual_signature": "Green optic slit, magenta mantle, recurved smartbow",
        "ability_detail": "Overwrites a construct or cantor and turns it against nearby hostiles.",
        "weapon_detail": "Long-range smartbow with a concealed data dagger for emergencies.",
        "height": "1.69 m",
        "actor_scale": 1.10,
        "recovery_affinity": 0.62,
        "guild_epithet": "THE EYE OUTSIDE THE MAP",
        "field_quote": "Every locked route is just a system admitting fear.",
        "crest": "OPEN SIGNAL EYE",
    },
    "morrow": {
        "name": "MORROW-9",
        "title": "ECHO WARDEN",
        "color": (255, 112, 182),
        "accent": (102, 242, 207),
        "max_hp": 144,
        "speed": 194.0,
        "damage": 23.0,
        "range": 224.0,
        "attack_cooldown": 0.54,
        "strength": "Reanimates defeated hosts / flexible support pressure",
        "weakness": "Repeated echo use accumulates corruption and drains resolve",
        "ability": "ECHO REVENANT",
        "weapon": "Gravecaster staff + shard sickle",
        "discipline": 0.72,
        "caution": 0.63,
        "tech": 0.78,
        "arcana": 0.99,
        "aggression": 0.52,
        "altruism": 0.76,
        "resolve": 0.74,
        "curiosity": 0.88,
        "protectiveness": 0.70,
        "personality": ["MORBIDLY CURIOUS", "ADAPTIVE", "CORRUPTION-PRONE"],
        "doctrine": "Turns fallen enemies into short-lived allies before committing to direct combat.",
        "origin": "MORTUARY CLOUD / NINTH FORBIDDEN RESTORATION",
        "body": "Tall funerary synth with a suspended echo reliquary",
        "armor": "Segmented mourning plate / exposed soul-conduit ribs",
        "visual_signature": "Rose death-mask, mint reliquary rings, hooked gravecaster staff",
        "ability_detail": "Reboots one defeated hostile as a temporary echo that attacks its former allies.",
        "weapon_detail": "Mid-range gravecaster staff with a hooked shard sickle for close defense.",
        "height": "1.92 m",
        "actor_scale": 1.18,
        "recovery_affinity": 0.54,
        "guild_epithet": "THE WARDEN OF SECOND DEATHS",
        "field_quote": "Nothing is gone. Some things only need a worse invitation.",
        "crest": "NINTH RELIQUARY",
    },
}

QUESTS: dict[str, dict[str, Any]] = {
    "purge": {
        "name": "ASHEN CHOIR PURGE",
        "type": "PURGE CONTRACT",
        "danger": "HIGH",
        "color": (255, 72, 102),
        "brief": "Destroy the revenant choir occupying Saint Voltage Cathedral.",
        "threats": ["Melee revenants", "Security constructs", "Arcane cantors"],
        "recommend": ["Sustained combat", "Crowd control", "Corruption resistance"],
        "reward": "2,100 CREDITS + RELIC CACHE",
        "base_credits": 2100,
        "base_renown": 4,
    },
    "recovery": {
        "name": "THE BLACKGLASS RELIC",
        "type": "RECOVERY CONTRACT",
        "danger": "SEVERE",
        "color": (180, 96, 255),
        "brief": "Recover a sealed memory reliquary and return to extraction.",
        "threats": ["Patrolling constructs", "Curse fields", "Unknown guardian"],
        "recommend": ["Mobility", "Perception", "Route discipline"],
        "reward": "2,800 CREDITS + MEMORY SHARD",
        "base_credits": 2800,
        "base_renown": 5,
    },
    "rescue": {
        "name": "CHOIR OF THE MISSING",
        "type": "RESCUE CONTRACT",
        "danger": "ELEVATED",
        "color": (56, 224, 204),
        "brief": "Locate three trapped pilgrims and escort them to the gate.",
        "threats": ["Revenant patrols", "Ranged sentries", "Civilian panic"],
        "recommend": ["Protection", "Discipline", "Threat interception"],
        "reward": "2,400 CREDITS + GUILD FAVOR",
        "base_credits": 2400,
        "base_renown": 6,
    },
}


HERO_ORDERS: dict[str, dict[str, Any]] = {
    "balanced": {
        "name": "TRUST INSTINCT",
        "short": "BALANCED",
        "color": (120, 190, 230),
        "brief": "No tactical pressure. The hero follows their natural doctrine.",
        "aligned": {"VERIFYING CLEARANCE", "SEEKING RELIQUARY", "RETURNING TO GATE", "LOCATING PILGRIM", "ESCORTING SURVIVORS", "HUNTING HOSTILE", "INTERCEPTING THREAT", "CONFRONTING SOVEREIGN"},
    },
    "objective": {
        "name": "SECURE OBJECTIVE",
        "short": "OBJECTIVE",
        "color": (92, 235, 255),
        "brief": "Favor mission progress over optional combat and curiosity.",
        "aligned": {"SEEKING RELIQUARY", "RETURNING TO GATE", "LOCATING PILGRIM", "ESCORTING SURVIVORS", "VERIFYING CLEARANCE", "CONFRONTING SOVEREIGN"},
    },
    "protect": {
        "name": "PROTECT LIVES",
        "short": "PROTECT",
        "color": (92, 255, 184),
        "brief": "Prioritize civilians, threat interception, and safe extraction.",
        "aligned": {"LOCATING PILGRIM", "INTERCEPTING THREAT", "ESCORTING SURVIVORS", "SANCTUARY PROTOCOL"},
    },
    "eliminate": {
        "name": "ELIMINATE THREATS",
        "short": "ELIMINATE",
        "color": (255, 104, 132),
        "brief": "Apply pressure to hostiles even when a cleaner route exists.",
        "aligned": {"HUNTING HOSTILE", "CLEARING ROUTE", "FINISHING WOUNDED TARGET", "SETTING GHOST OVERRIDE", "CONFRONTING SOVEREIGN"},
    },
    "survive": {
        "name": "PRESERVE HERO",
        "short": "SURVIVE",
        "color": (255, 210, 104),
        "brief": "Retreat sooner, avoid concentrated threats, and conserve resolve.",
        "aligned": {"TACTICAL WITHDRAWAL", "EVADING DIRECT PRESSURE", "RETURNING TO GATE", "ESCORTING SURVIVORS"},
    },
}

CONTRACT_COMPLICATIONS: dict[str, dict[str, Any]] = {
    "purge": {
        "key": "choir_reinforcements",
        "name": "CHOIR REINFORCEMENTS",
        "color": (255, 82, 126),
        "brief": "A dormant summoning circuit reactivates after the choir takes losses.",
        "trigger": "THREE HOSTILES DESTROYED",
    },
    "recovery": {
        "key": "reliquary_backlash",
        "name": "RELIQUARY BACKLASH",
        "color": (205, 102, 255),
        "brief": "Securing the memory reliquary reroutes extraction and wakes its guardians.",
        "trigger": "RELIC SECURED",
    },
    "rescue": {
        "key": "pilgrim_panic",
        "name": "PILGRIM PANIC",
        "color": (84, 245, 210),
        "brief": "The first rescue link triggers a panic surge and a hostile ambush.",
        "trigger": "FIRST PILGRIM LINKED",
    },
}



MISSION_ENVIRONMENTS: dict[str, dict[str, Any]] = {
    "purge": {
        "site": "SAINT VOLTAGE CATHEDRAL",
        "district": "LOWER NEON WARD",
        "client": "ORDER OF THE LAST CIRCUIT",
        "site_code": "NAVE-13 / ASH CHOIR",
        "identity": "A ruined voltage cathedral where corrupted hymns animate the dead.",
        "floor": (20, 12, 24),
        "grid": (58, 31, 58),
        "wall": (45, 22, 42),
        "edge": (176, 58, 105),
        "accent": (255, 74, 112),
        "secondary": (255, 177, 76),
        "fog": (84, 18, 38),
        "landmarks": ["CHOIR PIT", "BROKEN SAINTS", "ASH BRAZIERS"],
        "hazard": "CORRUPTED LITURGY",
        "weather": "FALLING ASH / HARMONIC STATIC",
    },
    "recovery": {
        "site": "BLACKGLASS MEMORY VAULT",
        "district": "ARCHIVE NULL",
        "client": "GUILD RELIQUARY OFFICE",
        "site_code": "VAULT-7 / MIRROR INDEX",
        "identity": "An obsidian archive that reflects erased memories through fractured glass lanes.",
        "floor": (10, 13, 27),
        "grid": (31, 39, 70),
        "wall": (26, 22, 49),
        "edge": (112, 77, 176),
        "accent": (184, 94, 255),
        "secondary": (92, 229, 255),
        "fog": (42, 25, 92),
        "landmarks": ["MEMORY WELL", "MIRROR STACKS", "NULL TRANSEPT"],
        "hazard": "REFLECTIVE CURSE FIELDS",
        "weather": "GLASS DUST / DATA AFTERIMAGES",
    },
    "rescue": {
        "site": "PILGRIM TRANSIT OSSUARY",
        "district": "OLD MERCY LINE",
        "client": "FREE PILGRIM RELAY",
        "site_code": "PLATFORM-4 / LOST CHOIR",
        "identity": "A collapsed sanctuary station where survivors hide among abandoned reliquary trains.",
        "floor": (9, 21, 26),
        "grid": (22, 56, 58),
        "wall": (18, 42, 47),
        "edge": (54, 145, 139),
        "accent": (66, 231, 202),
        "secondary": (255, 191, 92),
        "fog": (17, 74, 72),
        "landmarks": ["MERCY PLATFORM", "RELIC CARRIAGES", "SURVIVOR SHRINES"],
        "hazard": "PANIC RESONANCE",
        "weather": "COOLANT RAIN / DISTANT SIGNAL BELLS",
    },
}


ENEMY_VARIANTS: dict[str, dict[str, dict[str, Any]]] = {
    "purge": {
        "revenant": {
            "name": "ASHBOUND CHORISTER", "role": "MELEE ZEALOT",
            "origin": "Choir corpse fused to a live ember hymn", "body": "Charred vestments, cinder crown, exposed hex-ribs",
            "weapon": "Voltage cleaver and burning grasp", "behavior": "Rushes the nearest living signal and strengthens around choir deaths",
            "weakness": "Cinder joints flare before every committed strike", "color": (255, 72, 110), "accent": (255, 184, 70), "mark": "EMBER CROWN",
        },
        "construct": {
            "name": "NAVE BULWARK", "role": "RANGED CHOIR SENTINEL",
            "origin": "Cathedral defense chassis rewritten as a mobile hymn wall", "body": "Brass-black armor, shoulder hymn shields, amber projector core",
            "weapon": "Liturgical bolt projector", "behavior": "Locks long nave lanes and shields nearby cantors",
            "weakness": "Rear prayer core remains vulnerable to machine override", "color": (255, 174, 56), "accent": (255, 234, 136), "mark": "HYMN SHIELDS",
        },
        "cantor": {
            "name": "CINDER PRELATE", "role": "CHOIR SUPPORT CHANNELER",
            "origin": "A senior liturgy intelligence bound to a cremation shell", "body": "Floating black robes around a furnace-violet core",
            "weapon": "Ash staff and restorative chorus", "behavior": "Repairs the choir and accelerates the summoning circuit",
            "weakness": "Flame halo collapses when isolated", "color": (214, 80, 255), "accent": (255, 112, 88), "mark": "FLAME HALO",
        },
    },
    "recovery": {
        "revenant": {
            "name": "BLACKGLASS HUSK", "role": "MIRROR PURSUER",
            "origin": "An erased archivist reconstructed from incomplete reflections", "body": "Obsidian skin, mirrored face shards, archive tags",
            "weapon": "Glass hook and memory claws", "behavior": "Tracks the reliquary carrier through reflected positions",
            "weakness": "False reflections briefly lag behind the true body", "color": (176, 88, 255), "accent": (90, 232, 255), "mark": "SHARD MASK",
        },
        "construct": {
            "name": "INDEX SENTINEL", "role": "VAULT RANGE CONTROLLER",
            "origin": "Archive catalog chassis guarding forbidden memory addresses", "body": "Dark prism plates, rotating lens fins, cyan index core",
            "weapon": "Prismatic memory lance", "behavior": "Repositions to keep the reliquary inside a firing corridor",
            "weakness": "Lens fins broadcast the next firing lane", "color": (108, 215, 255), "accent": (200, 104, 255), "mark": "INDEX FINS",
        },
        "cantor": {
            "name": "MEMORY PRELATE", "role": "ARCHIVE RESTORATION HOST",
            "origin": "A preservation intelligence that treats intruders as corrupted records", "body": "Violet robe frame surrounded by rotating memory rings",
            "weapon": "Recall staff and recursive repair pulse", "behavior": "Restores damaged guardians and rewrites extraction routes",
            "weakness": "Memory rings expose the core during each rewrite", "color": (222, 91, 255), "accent": (105, 244, 229), "mark": "MEMORY RINGS",
        },
    },
    "rescue": {
        "revenant": {
            "name": "MERCY-LINE SHADE", "role": "SURVIVOR HUNTER",
            "origin": "A failed pilgrim evacuation imprint hardened into a predator", "body": "Transit robes, restraint chains, pale signal face",
            "weapon": "Chain sickle and panic claws", "behavior": "Targets isolated civilians before confronting the hero",
            "weakness": "Restraint chain catches on wide turns", "color": (88, 240, 202), "accent": (255, 164, 92), "mark": "CHAIN COLLAR",
        },
        "construct": {
            "name": "PLATFORM WARDER", "role": "ESCORT DENIAL SENTINEL",
            "origin": "Transit security unit still enforcing a dead evacuation order", "body": "Teal restraint frame, warning cage, orange route lamp",
            "weapon": "Suppression pulse emitter", "behavior": "Cuts civilian follow lanes and fires into crowded routes",
            "weakness": "Route lamp exposes its current suppression lane", "color": (76, 214, 195), "accent": (255, 193, 88), "mark": "WARNING CAGE",
        },
        "cantor": {
            "name": "PANIC WEAVER", "role": "CIVILIAN DISRUPTION HOST",
            "origin": "A choir signal grown from trapped evacuation distress", "body": "Thin floating vestments with branching resonance tendrils",
            "weapon": "Fear chorus and restorative pulse", "behavior": "Raises civilian panic while repairing nearby warders",
            "weakness": "Tendrils brighten before every panic surge", "color": (188, 91, 255), "accent": (80, 246, 210), "mark": "PANIC TENDRILS",
        },
    },
}


SIGNATURE_BOSSES: dict[str, dict[str, Any]] = {
    "purge": {
        "id": "ash_saint", "name": "THE ASH SAINT", "kind": "revenant",
        "role": "CATHEDRAL EXECUTIONER", "title": "LAST VOICE OF SAINT VOLTAGE",
        "origin": "A canonized war chassis carrying the cathedral's surviving choir core.",
        "body": "Towering ash plate, split saint halo, six burning reliquary seals.",
        "weapon": "Processional cleaver and harmonic shockwave",
        "behavior": "Charges wounded targets, then releases a close-range choir rupture below half integrity.",
        "weakness": "The split halo exposes its choir core during each rupture.",
        "color": (255, 82, 108), "accent": (255, 214, 98), "mark": "SAINT HALO",
        "hp": 122.0, "speed": 84.0, "damage": 11.0, "range": 68.0, "delay": 0.86, "radius": 34.0,
        "phase_two": "CHOIR RUPTURE", "intro": "THE LAST SAINT HAS ANSWERED THE PURGE.",
    },
    "recovery": {
        "id": "mirror_abbot", "name": "THE MIRROR ABBOT", "kind": "construct",
        "role": "BLACKGLASS VAULT SOVEREIGN", "title": "KEEPER OF THE UNREMEMBERED",
        "origin": "The archive's final curator rebuilt around a forbidden memory index.",
        "body": "Obsidian pontiff frame, mirrored wing-fins, rotating cyan vault eye.",
        "weapon": "Prismatic lance and reflected firing lanes",
        "behavior": "Creates mirrored shot lanes and accelerates fire after the reliquary is disturbed.",
        "weakness": "Its true vault eye brightens while false reflections reposition.",
        "color": (170, 98, 255), "accent": (96, 238, 255), "mark": "MIRROR WINGS",
        "hp": 118.0, "speed": 52.0, "damage": 8.5, "range": 340.0, "delay": 1.28, "radius": 36.0,
        "phase_two": "REFLECTION CASCADE", "intro": "THE VAULT HAS APPOINTED A FINAL KEEPER.",
    },
    "rescue": {
        "id": "last_conductor", "name": "THE LAST CONDUCTOR", "kind": "cantor",
        "role": "OSSUARY PANIC SOVEREIGN", "title": "MASTER OF THE DEAD MERCY LINE",
        "origin": "A transit command intelligence fused with every failed evacuation signal.",
        "body": "Long conductor vestments, signal crown, branching route tendrils.",
        "weapon": "Panic bell, repair chorus, and route-severing pulse",
        "behavior": "Heals escorts' pursuers and releases panic waves when civilians gather near extraction.",
        "weakness": "Its crown opens while broadcasting a panic wave.",
        "color": (92, 235, 204), "accent": (255, 190, 92), "mark": "SIGNAL CROWN",
        "hp": 112.0, "speed": 58.0, "damage": 8.0, "range": 285.0, "delay": 1.22, "radius": 33.0,
        "phase_two": "FINAL DEPARTURE", "intro": "THE MERCY LINE'S LAST CONDUCTOR HAS ARRIVED.",
    },
}


HERO_LINKS: dict[str, dict[str, Any]] = {
    "nyx": {
        "name": "EXECUTION SIGNAL", "color": HEROES["nyx"]["color"],
        "brief": "NYX shadows the contract feed and marks exposed targets for a finishing strike.",
        "effect": "+6% damage; additional damage against targets below 30% integrity.",
        "relationship": "A dangerous promise that the deployed hero will leave nothing unfinished.",
    },
    "circuit": {
        "name": "SANCTUARY UPLINK", "color": HEROES["circuit"]["color"],
        "brief": "Circuit anchors the remote channel with a protective prayer checksum.",
        "effect": "+8% conditioned vitality and reduced boss shock damage.",
        "relationship": "A solemn vow that someone remains awake on the other side of the gate.",
    },
    "vesper": {
        "name": "GHOSTLINE OVERWATCH", "color": HEROES["vesper"]["color"],
        "brief": "Vesper maps firing lanes and whispers safe angles into the hero's optics.",
        "effect": "+10% attack range and 5% faster attack recovery.",
        "relationship": "Trust expressed as coordinates, timing windows, and one open route.",
    },
    "morrow": {
        "name": "ECHO VIGIL", "color": HEROES["morrow"]["color"],
        "brief": "MORROW keeps a funerary channel open for resolve recovery and echo control.",
        "effect": "+6 resolve ceiling; corruption decays faster during the mission.",
        "relationship": "A reminder that even the dead are not required to face the dark alone.",
    },
}


STORY_CHAIN: dict[str, Any] = {
    "id": "night_of_three_sovereigns",
    "name": "NIGHT OF THREE SOVEREIGNS",
    "subtitle": "A linked guild operation following one surviving signal across three contract sites.",
    "order": ["purge", "recovery", "rescue"],
    "chapters": {
        "purge": {
            "name": "ASH TESTAMENT",
            "brief": "Break the Ash Saint and silence the transmission hidden inside Saint Voltage.",
            "aftermath": "CHOIR SILENCE",
            "carry": "The severed hymn clears Blackglass interference and steadies the next operative.",
        },
        "recovery": {
            "name": "BLACKGLASS REQUIEM",
            "brief": "Use the silence to recover the forbidden index guarded by the Mirror Abbot.",
            "aftermath": "OPEN INDEX",
            "carry": "The recovered index exposes survivor routes beneath the Mercy Line panic field.",
        },
        "rescue": {
            "name": "MERCY LINE CODA",
            "brief": "Follow the index, end the Last Conductor, and reopen the route for the next cycle.",
            "aftermath": "MERCY ROUTE",
            "carry": "The reopened line gives the next cycle a faster, clearer insertion route.",
        },
    },
    "completion_credits": 1500,
    "completion_renown": 4,
}


SOVEREIGN_AFTERMATHS: dict[str, dict[str, Any]] = {
    "none": {
        "name": "NO ACTIVE AFTERMATH",
        "color": (112, 132, 160),
        "brief": "This contract is not receiving a carryover effect from the linked operation.",
        "effect": "NONE",
    },
    "choir_silence": {
        "name": "CHOIR SILENCE",
        "color": (255, 168, 104),
        "brief": "The Ash Saint's broken hymn no longer crowds the Blackglass channel.",
        "effect": "+8 starting resolve and +4 resolve ceiling.",
    },
    "open_index": {
        "name": "OPEN INDEX",
        "color": (112, 232, 255),
        "brief": "The Mirror Abbot's forbidden index reveals stable survivor lanes through the ossuary.",
        "effect": "Civilian panic pressure reduced by 25%.",
    },
    "mercy_route": {
        "name": "MERCY ROUTE",
        "color": (104, 255, 194),
        "brief": "The restored transit route accelerates the next assault on Saint Voltage.",
        "effect": "+7% movement speed and +5 starting resolve.",
    },
}


BOND_EVENTS: dict[str, dict[str, Any]] = {
    "nyx|circuit": {
        "name": "THE KNIFE AND THE CHAPEL",
        "prompt": "Circuit asks NYX to promise that survival still matters after the target falls.",
        "anchor": "NYX leaves one escape route open. Circuit records it as trust.",
        "boundary": "They keep the link tactical and let the medbay absorb the strain.",
        "color": (255, 188, 102),
    },
    "nyx|vesper": {
        "name": "TWO ROUTES, ONE EXIT",
        "prompt": "Vesper confronts NYX about repeatedly abandoning the safest route for the final strike.",
        "anchor": "They agree on one shared extraction coordinate before every contract.",
        "boundary": "Vesper closes the personal channel and keeps only target telemetry.",
        "color": (126, 238, 214),
    },
    "nyx|morrow": {
        "name": "THE SECOND KILL",
        "prompt": "MORROW asks whether a resurrected enemy has already paid for the life NYX took.",
        "anchor": "NYX accepts the echo as a second responsibility, not a second target.",
        "boundary": "They separate execution data from funerary rites and recover in silence.",
        "color": (255, 116, 182),
    },
    "circuit|vesper": {
        "name": "SANCTUARY IN STATIC",
        "prompt": "Circuit offers Vesper a permanent refuge channel she cannot erase from the map.",
        "anchor": "Vesper accepts one fixed coordinate that will always answer.",
        "boundary": "She keeps the channel temporary and the medbay clears the shared fatigue.",
        "color": (104, 226, 255),
    },
    "circuit|morrow": {
        "name": "LAST RITES FOR MACHINES",
        "prompt": "Circuit challenges MORROW to name the difference between restoration and captivity.",
        "anchor": "They author a rite that every raised echo must be allowed to end.",
        "boundary": "They suspend theological debate and decompress under separate wards.",
        "color": (212, 188, 255),
    },
    "vesper|morrow": {
        "name": "THE ARCHIVE THAT BREATHES",
        "prompt": "Vesper discovers that MORROW remembers deleted mission paths as if they were voices.",
        "anchor": "They create a shared archive where dangerous memories can be witnessed together.",
        "boundary": "Vesper seals the archive and orders a controlled recovery interval.",
        "color": (154, 255, 194),
    },
}


def enemy_variant(quest_key: str, kind: str) -> dict[str, Any]:
    return ENEMY_VARIANTS.get(quest_key, {}).get(kind, ENEMY_ARCHETYPES[kind])


EQUIPMENT_KITS: dict[str, dict[str, Any]] = {
    "aegis": {
        "name": "SANCTUM AEGIS",
        "type": "DEFENSIVE RELIC",
        "color": (255, 205, 92),
        "brief": "Layered ward plates absorb concentrated punishment but slow route changes.",
        "effects": ["+22% conditioned vitality", "-7% movement speed", "Reduced first complication shock"],
        "best_for": ["purge", "rescue"],
        "risk": "May delay extraction on mobility-heavy contracts.",
    },
    "surveyor": {
        "name": "GHOSTLINE SURVEYOR",
        "type": "INTELLIGENCE RIG",
        "color": (94, 238, 255),
        "brief": "Maps hostile channels and stabilizes long-range targeting before deployment.",
        "effects": ["+18% attack range", "+8 resolve", "Higher confidence in hidden threat intel"],
        "best_for": ["recovery", "purge"],
        "risk": "No emergency protection if the hero is cornered.",
    },
    "beacon": {
        "name": "PILGRIM BEACON",
        "type": "ESCORT RELAY",
        "color": (96, 255, 190),
        "brief": "A calming signal link improves civilian cohesion and protective response.",
        "effects": ["Faster civilian follow", "Reduced civilian panic", "+12% protective utility"],
        "best_for": ["rescue"],
        "risk": "Provides little value when no civilians are present.",
    },
    "ampoule": {
        "name": "VOIDGLASS AMPOULE",
        "type": "EMERGENCY CONSUMABLE",
        "color": (220, 102, 255),
        "brief": "Automatically reconstructs damaged tissue once, then inflicts neural stress.",
        "effects": ["One automatic 34% heal", "+15 stress after activation", "No movement penalty"],
        "best_for": ["purge", "recovery", "rescue"],
        "risk": "The recovery shock can push a low-resolve hero toward withdrawal.",
    },
}

QUEST_INTEL: dict[str, dict[str, Any]] = {
    "purge": {
        "confirmed": ["Seven choir signatures", "Mixed melee and ranged contacts", "Corruption field active"],
        "probable": ["Dormant summoning circuit may react to casualties"],
        "unknown": "Source of the third harmonic remains unverified.",
    },
    "recovery": {
        "confirmed": ["Reliquary located in east transept", "Construct patrols remain active", "Primary extraction gate online"],
        "probable": ["Artifact removal may alter the route"],
        "unknown": "Guardian classification is missing from the archive.",
    },
    "rescue": {
        "confirmed": ["Three living pilgrim signals", "Ranged sentries cover two lanes", "Civilians display elevated panic"],
        "probable": ["First rescue link may expose the remaining pilgrims"],
        "unknown": "One signal periodically disappears behind choir interference.",
    },
}


def equipment_fit(equipment_key: str, hero_key: str, quest_key: str) -> dict[str, Any]:
    if equipment_key not in EQUIPMENT_KITS:
        raise ValueError("Unknown equipment kit")
    kit = EQUIPMENT_KITS[equipment_key]
    score = 0.54
    if quest_key in kit["best_for"]:
        score += 0.25
    if equipment_key == "aegis" and hero_key == "circuit":
        score += 0.08
    if equipment_key == "surveyor" and hero_key == "vesper":
        score += 0.10
    if equipment_key == "beacon" and hero_key == "circuit":
        score += 0.07
    if equipment_key == "ampoule" and HEROES[hero_key]["max_hp"] < 120:
        score += 0.08
    if equipment_key == "surveyor" and hero_key == "morrow":
        score += 0.07
    if equipment_key == "ampoule" and hero_key == "morrow":
        score += 0.05
    if equipment_key == "aegis" and quest_key == "recovery":
        score -= 0.12
    if equipment_key == "beacon" and quest_key != "rescue":
        score -= 0.22
    score = max(0.18, min(0.98, score))
    if score >= 0.82:
        rating = "EXCELLENT MATCH"
    elif score >= 0.68:
        rating = "STRONG MATCH"
    elif score >= 0.50:
        rating = "CONDITIONAL"
    else:
        rating = "LOW VALUE"
    return {"score": score, "percent": int(round(score * 100)), "rating": rating, "color": kit["color"]}

def recovery_quote(hero_key: str, strain: float) -> dict[str, Any]:
    """Return deterministic medbay cost and expected strain reduction."""
    if hero_key not in HEROES:
        raise ValueError("Unknown hero")
    strain = max(0.0, min(100.0, float(strain)))
    affinity = float(HEROES[hero_key].get("recovery_affinity", 0.7))
    reduction = 0 if strain <= 0 else min(int(round(strain)), 18 + int(round(affinity * 12)))
    cost = 0 if reduction <= 0 else 140 + int(round(strain * 14.0)) + int(round((1.0 - affinity) * 180.0))
    return {
        "cost": cost,
        "reduction": reduction,
        "remaining": max(0, int(round(strain)) - reduction),
        "ready": reduction > 0,
    }


def recovery_state(hero_key: str, strain: float) -> dict[str, Any]:
    """Hero-specific persistent injury state used by AI, stats, and roster presentation."""
    strain = max(0.0, min(100.0, float(strain)))
    if strain < 15:
        return {"name": "COMBAT READY", "severity": 0, "summary": "No persistent field impairment."}
    severe = strain >= 45
    states = {
        "nyx": ("PHASE FRACTURE", "Aggression rises while caution and phase stability fall."),
        "circuit": ("RELIQUARY OVERLOAD", "Heavy ward systems slow route changes but reinforce sanctuary output."),
        "vesper": ("SIGNAL TREMOR", "Long-range precision degrades and withdrawal instincts sharpen."),
        "morrow": ("ECHO SATURATION", "Residual dead-code raises starting corruption and weakens resolve."),
    }
    name, summary = states[hero_key]
    if severe:
        name = "SEVERE " + name
    return {"name": name, "severity": 2 if severe else 1, "summary": summary}


def contract_reward(quest_key: str, status: str, elapsed: float, hp_ratio: float,
                    complication_resolved: bool, order_status: str) -> dict[str, Any]:
    """Calculate a transparent guild payout from real mission outcomes."""
    if quest_key not in QUESTS:
        raise ValueError("Unknown quest")
    q = QUESTS[quest_key]
    base = int(q["base_credits"])
    renown = int(q["base_renown"])
    notes: list[str] = []
    if status != "SUCCESS":
        salvage = max(90, int(round(base * 0.12)))
        return {"credits": salvage, "renown": 0, "notes": ["RECOVERY SALVAGE"]}
    credits = base
    if elapsed <= 70.0:
        credits += 280
        notes.append("SWIFT COMPLETION +280")
    if hp_ratio >= 0.72:
        credits += 220
        renown += 1
        notes.append("HERO PRESERVED +220")
    if complication_resolved:
        credits += 180
        renown += 1
        notes.append("COMPLICATION CONTAINED +180")
    if order_status == "COMPLYING":
        credits += 120
        notes.append("ORDER DISCIPLINE +120")
    return {"credits": credits, "renown": renown, "notes": notes or ["BASE CONTRACT PAYOUT"]}


def quest_fit(hero_key: str, quest_key: str) -> dict[str, Any]:
    """Return deterministic hero/quest compatibility and readable reasoning."""
    h = HEROES[hero_key]
    hp_norm = min(1.0, float(h["max_hp"]) / 176.0)
    speed_norm = min(1.0, float(h["speed"]) / 236.0)
    damage_norm = min(1.0, float(h["damage"]) / 28.0)

    if quest_key == "purge":
        score = (
            h["aggression"] * 0.25
            + h["resolve"] * 0.18
            + h["arcana"] * 0.18
            + h["discipline"] * 0.11
            + damage_norm * 0.14
            + hp_norm * 0.14
        )
        positives = [
            (h["aggression"], "presses hostile advantage"),
            (h["arcana"], "resists choir corruption"),
            (hp_norm, "can survive sustained contact"),
        ]
        negatives = [
            (1.0 - h["aggression"], "may avoid necessary combat"),
            (1.0 - hp_norm, "limited margin under concentrated fire"),
        ]
    elif quest_key == "recovery":
        score = (
            h["tech"] * 0.24
            + h["caution"] * 0.20
            + h["discipline"] * 0.17
            + h["curiosity"] * 0.14
            + speed_norm * 0.14
            + h["resolve"] * 0.11
        )
        positives = [
            (h["tech"], "can exploit security hosts"),
            (h["caution"], "avoids unnecessary engagements"),
            (speed_norm, "reaches extraction efficiently"),
        ]
        negatives = [
            (1.0 - h["discipline"], "may abandon the relic route"),
            (1.0 - h["caution"], "may overcommit before extraction"),
        ]
    else:
        score = (
            h["altruism"] * 0.25
            + h["protectiveness"] * 0.23
            + h["discipline"] * 0.18
            + h["resolve"] * 0.12
            + h["caution"] * 0.10
            + hp_norm * 0.12
        )
        positives = [
            (h["protectiveness"], "intercepts threats near pilgrims"),
            (h["altruism"], "keeps civilian survival as a priority"),
            (h["discipline"], "maintains the escort objective"),
        ]
        negatives = [
            (1.0 - h["altruism"], "may value kills over civilians"),
            (1.0 - h["protectiveness"], "weak escort interception instinct"),
        ]

    score = max(0.0, min(1.0, float(score)))
    if score >= 0.78:
        rating, color = "SYNCHRONIZED", (92, 255, 184)
    elif score >= 0.65:
        rating, color = "STRONG", (108, 225, 255)
    elif score >= 0.52:
        rating, color = "VIABLE", (255, 218, 104)
    elif score >= 0.40:
        rating, color = "RISKY", (255, 146, 82)
    else:
        rating, color = "CRITICAL MISMATCH", (255, 80, 112)

    best = max(positives, key=lambda item: item[0])[1]
    risk = max(negatives, key=lambda item: item[0])[1]
    return {
        "score": score,
        "percent": int(round(score * 100)),
        "rating": rating,
        "color": color,
        "advantage": best,
        "risk": risk,
    }


ENEMY_ARCHETYPES: dict[str, dict[str, Any]] = {
    "revenant": {
        "name": "ASHEN REVENANT",
        "role": "MELEE PURSUER",
        "origin": "Choir corpse animated by corrupted liturgy",
        "body": "Desiccated humanoid under broken vestments",
        "weapon": "Ritual cleaver and grasping hex-claws",
        "behavior": "Closes distance and commits to repeated melee pressure",
        "weakness": "Short reach; vulnerable while crossing open lanes",
        "silhouette": "ragged humanoid",
    },
    "construct": {
        "name": "CHOIR SECURITY CONSTRUCT",
        "role": "RANGED SENTINEL",
        "origin": "Cathedral defense chassis carrying a stolen prayer core",
        "body": "Angular plated machine on reverse-jointed legs",
        "weapon": "Amber bolt projector",
        "behavior": "Maintains firing distance and controls long corridors",
        "weakness": "Machine host can be seized by Ghost Override",
        "silhouette": "angular machine",
    },
    "cantor": {
        "name": "ARCANE CANTOR",
        "role": "SUPPORT CHANNELER",
        "origin": "Choir intelligence nested inside a ceremonial shell",
        "body": "Floating robe frame around a violet resonance core",
        "weapon": "Resonance staff and restorative chorus",
        "behavior": "Repairs damaged allies before projecting ranged curses",
        "weakness": "Fragile when isolated from the choir",
        "silhouette": "robed channeler",
    },
}

CIVILIAN_ROLES: list[dict[str, str]] = [
    {
        "role": "ARCHIVE PILGRIM",
        "detail": "Carries sealed testimony recovered from the lower transept",
        "visual": "white mantle / cyan archive case",
    },
    {
        "role": "CHOIR DEFECTOR",
        "detail": "Former acolyte who disabled one of the cathedral alarms",
        "visual": "dark robe / broken amber insignia",
    },
    {
        "role": "RELIC MEDIC",
        "detail": "Field medic protecting anti-corruption ampoules",
        "visual": "pale coat / green medical satchel",
    },
]

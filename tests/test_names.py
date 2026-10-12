from pipeline.gamemaster import Move
from pipeline.names import TYPE_NAMES_FR, move_name, pokemon_name, split_form, sprite_id


def test_type_names_cover_all_18():
    assert len(TYPE_NAMES_FR) == 18 and TYPE_NAMES_FR["FIRE"] == "Feu" and TYPE_NAMES_FR["DARK"] == "Ténèbres"


def test_split_form():
    assert split_form(None) == (None, None)
    assert split_form("ALOLA") == ("ALOLA", None)
    assert split_form("GALARIAN_STANDARD") == ("GALARIAN", "STANDARD")
    assert split_form("ORIGIN") == (None, "ORIGIN")


def test_pokemon_names_fr_and_en(gm_fx, names_fx):
    b = gm_fx.by_id()
    cases = {
        "CHARIZARD": ("Dracaufeu", "Charizard"),
        "CHARIZARD_SHADOW": ("Dracaufeu Obscur", "Shadow Charizard"),
        "CHARIZARD_MEGA_Y": ("Méga-Dracaufeu Y", "Mega Charizard Y"),
        "RAICHU_ALOLA": ("Raichu d'Alola", "Alolan Raichu"),
        "DARMANITAN_GALARIAN_STANDARD": ("Darumacho de Galar (Standard)", "Galarian Darmanitan (Standard)"),
        "KYOGRE_PRIMAL": ("Primo-Kyogre", "Primal Kyogre"),
        "GIRATINA_ORIGIN": ("Giratina (Origin)", "Giratina (Origin)"),
        "MEWTWO_A": ("Mewtwo (Armored)", "Mewtwo (Armored)"),
        "DITTO": ("Métamorph", "Ditto"),
    }
    for pid, (fr, en) in cases.items():
        assert pokemon_name(b[pid], names_fx, "fr") == fr, pid
        assert pokemon_name(b[pid], names_fx, "en") == en, pid


def test_move_names(gm_fx, names_fx):
    assert move_name(gm_fx.moves["BLAST_BURN"], names_fx, "fr") == "Rafale Feu"
    assert move_name(gm_fx.moves["BLAST_BURN"], names_fx, "en") == "Blast Burn"
    assert move_name(gm_fx.moves["FIRE_SPIN_FAST"], names_fx, "fr") == "Danse Flammes"


def test_move_name_falls_back_to_english(names_fx):
    go_only = Move("AEROBLAST_PLUS", "FLYING", 200.0, 3500, -100)
    assert move_name(go_only, names_fx, "fr") == "Aéroblast +"            # base name found, "+" kept
    assert move_name(Move("ZZZ_GO_ONLY", "NORMAL", 1.0, 1000, -33), names_fx, "fr") == "Zzz Go Only"
    assert move_name(Move("WEIRD_THING_FAST", "NORMAL", 1.0, 1000, 1), names_fx, "en") == "Weird Thing"


def test_sprite_ids(gm_fx, names_fx):
    b = gm_fx.by_id()
    ids = names_fx.pokemon_ids
    assert sprite_id(b["CHARIZARD"], names_fx) == 6
    assert sprite_id(b["CHARIZARD_SHADOW"], names_fx) == 6
    assert sprite_id(b["CHARIZARD_MEGA_X"], names_fx) == ids["charizard-mega-x"]
    assert sprite_id(b["CHARIZARD_MEGA_Y"], names_fx) == ids["charizard-mega-y"]
    assert sprite_id(b["RAICHU_ALOLA"], names_fx) == ids["raichu-alola"]
    assert sprite_id(b["DARMANITAN_GALARIAN_STANDARD"], names_fx) == ids["darmanitan-galar-standard"]
    assert sprite_id(b["ROTOM_WASH"], names_fx) == ids["rotom-wash"]
    assert sprite_id(b["KYOGRE_PRIMAL"], names_fx) == ids["kyogre-primal"]
    assert sprite_id(b["MEWTWO_A"], names_fx) == 150     # no PokeAPI form → species sprite


def test_go_move_variants_get_french_names(names_fx):
    # Fixture lacks these PokeAPI rows, so build a tiny Names with the real identifiers.
    from pipeline.names import Names
    n = Names({}, {}, {}, {"future-sight": "Prescience", "weather-ball": "Ball'Météo", "techno-blast": "Techno-Buster",
                          "sacred-fire": "Feu Sacré", "superpower": "Surpuissance", "pyro-ball": "Ballon Brûlant"},
              {"future-sight": "Future Sight", "weather-ball": "Weather Ball", "techno-blast": "Techno Blast",
               "sacred-fire": "Sacred Fire", "superpower": "Superpower", "pyro-ball": "Pyro Ball"}, {})
    assert move_name(Move("FUTURESIGHT", "PSYCHIC", 120.0, 2700, -100), n, "fr") == "Prescience"
    assert move_name(Move("SUPER_POWER", "FIGHTING", 85.0, 2000, -50), n, "fr") == "Surpuissance"
    assert move_name(Move("PYROBALL", "FIRE", 80.0, 2500, -50), n, "fr") == "Ballon Brûlant"
    assert move_name(Move("WEATHER_BALL_FIRE", "FIRE", 55.0, 1600, -33), n, "fr") == "Ball'Météo (Feu)"
    assert move_name(Move("WEATHER_BALL_FIRE", "FIRE", 55.0, 1600, -33), n, "en") == "Weather Ball (Fire)"
    assert move_name(Move("TECHNO_BLAST_CHILL", "ICE", 120.0, 2000, -50), n, "fr") == "Techno-Buster (Glace)"
    assert move_name(Move("SACRED_FIRE_PLUS_PLUS", "FIRE", 155.0, 2500, -100), n, "fr") == "Feu Sacré ++"
    assert move_name(Move("SACRED_FIRE_PLUS", "FIRE", 135.0, 2500, -100), n, "en") == "Sacred Fire +"


def test_type_named_forms_use_french_type(names_fx):
    from pipeline.gamemaster import Pokemon
    arceus = Pokemon("ARCEUS_FIRE", "ARCEUS", 493, "FIRE", ("FIRE",), 238, 238, 237)
    assert pokemon_name(arceus, names_fx, "fr").endswith("(Feu)")
    assert pokemon_name(arceus, names_fx, "en").endswith("(Fire)")


def test_sprite_id_trims_unknown_trailing_form_words(names_fx):
    from pipeline.gamemaster import Pokemon
    from pipeline.names import Names
    n = Names({}, {}, {800: "necrozma", 888: "zacian"}, {}, {},
              {"necrozma": 800, "necrozma-dusk": 10155, "zacian": 888, "zacian-crowned": 10188})
    dusk = Pokemon("NECROZMA_DUSK_MANE", "NECROZMA", 800, "DUSK_MANE", ("PSYCHIC", "STEEL"), 1, 1, 1)
    crowned = Pokemon("ZACIAN_CROWNED_SWORD", "ZACIAN", 888, "CROWNED_SWORD", ("FAIRY", "STEEL"), 1, 1, 1)
    assert sprite_id(dusk, n) == 10155 and sprite_id(crowned, n) == 10188

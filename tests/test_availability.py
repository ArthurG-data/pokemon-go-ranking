from pipeline.availability import FeedName, Now, load_feed, match, parse_feed_name


def test_parse_feed_name_variants():
    assert parse_feed_name("Charizard") == FeedName("Charizard")
    assert parse_feed_name("Mega Charizard Y") == FeedName("Charizard", mega="MEGA_Y")
    assert parse_feed_name("Mega Blastoise") == FeedName("Blastoise", mega="MEGA")
    assert parse_feed_name("Primal Kyogre") == FeedName("Kyogre", mega="PRIMAL")
    assert parse_feed_name("Shadow Landorus (Incarnate)") == FeedName("Landorus", shadow=True, note="Incarnate")
    assert parse_feed_name("Alolan Raichu") == FeedName("Raichu", region="ALOLA")
    assert parse_feed_name("Galarian Darmanitan (Standard)") == FeedName("Darmanitan", region="GALARIAN", note="Standard")
    assert parse_feed_name("Mr. Mime") == FeedName("Mr. Mime")


def test_load_feed_reads_three_files(feed_dir):
    feed = load_feed(feed_dir)
    kinds = [now.kind for _, now in feed]
    assert kinds.count("raid") == 6 and kinds.count("egg") == 1 and kinds.count("research") == 1
    assert (FeedName("Charmander"), Now("egg", "2 km eggs", "Charmander")) in feed
    assert (FeedName("Charmander"), Now("research", "Catch 5 Fire-types", "Charmander")) in feed   # HTML stripped


def test_match_rows_and_notes(gm_fx, names_fx, feed_dir):
    now_by_id, unmatched = match(gm_fx.pokemon, names_fx.species_en, load_feed(feed_dir))
    assert now_by_id["CHARIZARD_MEGA_Y"] == [Now("raid", "Mega Raids", "Mega Charizard Y")]
    assert "CHARIZARD" not in now_by_id and "CHARIZARD_MEGA_X" not in now_by_id
    assert now_by_id["MEWTWO_SHADOW"] == [Now("raid", "5-Star Raids", "Shadow Mewtwo")]
    assert "MEWTWO" not in now_by_id
    assert now_by_id["RAICHU_ALOLA"][0].who == "Alolan Raichu" and "RAICHU" not in now_by_id
    assert "GIRATINA" in now_by_id and "GIRATINA_ORIGIN" not in now_by_id       # note with no matching form → base
    assert "DARMANITAN_GALARIAN_STANDARD" in now_by_id and "DARMANITAN_GALARIAN_ZEN" not in now_by_id
    assert now_by_id["CHARMANDER"] == [Now("egg", "2 km eggs", "Charmander"),
                                       Now("research", "Catch 5 Fire-types", "Charmander")]
    assert unmatched == ["Nonexistmon"]


def test_match_reports_unmatched(gm_fx, names_fx):
    now_by_id, unmatched = match(gm_fx.pokemon, names_fx.species_en,
                                 [(FeedName("Nonexistmon"), Now("raid", "1-Star Raids", "Nonexistmon"))])
    assert now_by_id == {} and unmatched == ["Nonexistmon"]


def test_form_note_matches_whole_words_only():
    from pipeline.gamemaster import Pokemon
    rows = [Pokemon("INDEEDEE", "INDEEDEE", 876, None, ("PSYCHIC", "NORMAL"), 1, 1, 1),
            Pokemon("INDEEDEE_FEMALE", "INDEEDEE", 876, "FEMALE", ("PSYCHIC", "NORMAL"), 1, 1, 1)]
    feed = [(parse_feed_name("Indeedee (Male)"), Now("egg", "5 km eggs", "Indeedee (Male)")),
            (parse_feed_name("Indeedee (Female)"), Now("egg", "5 km eggs", "Indeedee (Female)"))]
    now_by_id, unmatched = match(rows, {876: "Indeedee"}, feed)
    assert [n.who for n in now_by_id["INDEEDEE"]] == ["Indeedee (Male)"]
    assert [n.who for n in now_by_id["INDEEDEE_FEMALE"]] == ["Indeedee (Female)"]


def test_feed_name_punctuation_and_pattern_numbers():
    from pipeline.gamemaster import Pokemon
    rows = [Pokemon("MIME_JR", "MIME_JR", 439, None, ("PSYCHIC", "FAIRY"), 1, 1, 1),
            Pokemon("SPINDA", "SPINDA", 327, None, ("NORMAL",), 1, 1, 1)]
    feed = [(parse_feed_name("Mime Jr"), Now("egg", "5 km eggs", "Mime Jr")),
            (parse_feed_name("Spinda 4"), Now("research", "Catch 5", "Spinda 4"))]
    now_by_id, unmatched = match(rows, {439: "Mime Jr.", 327: "Spinda"}, feed)
    assert unmatched == [] and "MIME_JR" in now_by_id and "SPINDA" in now_by_id

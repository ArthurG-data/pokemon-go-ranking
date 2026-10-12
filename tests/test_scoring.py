import pytest

from pipeline.gamemaster import Move
from pipeline.scoring import (DEFENDER_DELAY_MS, Stats, combo, defender_rating, hit_damage, level40_stats,
                              move_score, rating)

FAST = Move("TEST_FAST", "FIRE", 10.0, 1000, 10)
CHARGED = Move("TEST_CHARGED", "FIRE", 100.0, 2000, -50)
STATS = Stats(atk=200.0, dfn=150.0, hp=150)


def test_level40_stats():
    s = level40_stats(223, 173, 186)
    assert s.atk == pytest.approx((223 + 15) * 0.7903)
    assert s.dfn == pytest.approx((173 + 15) * 0.7903)
    assert s.hp == 158            # floor((186+15) * 0.7903) = floor(158.85)
    sh = level40_stats(223, 173, 186, shadow=True)
    assert sh.atk == pytest.approx(s.atk * 1.2) and sh.dfn == pytest.approx(s.dfn / 1.2) and sh.hp == s.hp


def test_hit_damage_floors_and_adds_one():
    assert hit_damage(10.0, 200.0, 180.0, 1.2) == 7      # floor(6.67) + 1
    assert hit_damage(100.0, 200.0, 180.0, 1.2) == 67    # floor(66.67) + 1
    assert hit_damage(0.0, 200.0, 180.0, 1.0) == 1


def test_move_score_applies_stab_and_delay():
    assert move_score(FAST, STATS, ("FIRE",)) == pytest.approx((7.0, 10.0))
    assert move_score(FAST, STATS, ("WATER",)).dps == pytest.approx(6.0)   # floor(5.56)+1 = 6, no STAB
    assert move_score(CHARGED, STATS, ("FIRE",)) == pytest.approx((33.5, 25.0))
    assert move_score(FAST, STATS, ("FIRE",), extra_ms=DEFENDER_DELAY_MS).dps == pytest.approx(7 / 3)
    assert move_score(Move("ZERO_FAST", "NORMAL", 0.0, 1000, 5), STATS, ()).dps == 0.0


def test_combo_dps_matches_hand_computation():
    # FDPS=7, FEPS=10, CDPS=33.5, CEPS=25, y=900/150=6, x=25+5=30, (0.5 - 30/150)=0.3
    # DPS = (7*25 + 33.5*10)/35 + (33.5-7)/35 * 0.3 * 6 = 14.5714 + 1.3629
    s = combo(FAST, CHARGED, STATS, ("FIRE",))
    assert s.dps == pytest.approx(15.934, abs=0.001)
    assert s.tdo == pytest.approx(15.934 * 150 / 6, abs=0.05)
    assert s.rating == pytest.approx(rating(s.dps, s.tdo))
    assert rating(s.dps, s.tdo) == pytest.approx((s.dps * s.tdo) ** 0.5)   # balanced: DPS and TDO weigh the same


def test_combo_effectiveness_raises_score():
    neutral = combo(FAST, CHARGED, STATS, ("FIRE",))
    strong = combo(FAST, CHARGED, STATS, ("FIRE",), 1.6, 1.6)
    weak = combo(FAST, CHARGED, STATS, ("FIRE",), 0.625, 0.625)
    assert weak.rating < neutral.rating < strong.rating


def test_combo_with_no_damage_or_no_energy_is_zero():
    assert combo(Move("TRANSFORM_FAST", "NORMAL", 0.0, 2000, 0), Move("STRUGGLE", "NORMAL", 35.0, 2000, 0),
                 STATS, ("NORMAL",)) == (0.0, 0.0, 0.0)
    assert rating(0.0, 0.0) == 0.0


def test_defender_rating_scale():
    blissey = level40_stats(129, 169, 496)
    assert 30 < defender_rating(5.0, blissey) < 90
    assert defender_rating(0.0, blissey) == 0.0


def test_defender_rating_favours_bulk_over_damage():
    blissey = level40_stats(129, 169, 496)      # huge HP, weak attack (defender DPS ≈ 3.5)
    mewtwo = level40_stats(300, 182, 214)       # glass cannon (defender DPS ≈ 9.6)
    snorlax = level40_stats(190, 169, 330)      # defender DPS ≈ 4.9
    assert defender_rating(3.5, blissey) > defender_rating(4.9, snorlax) > defender_rating(9.6, mewtwo)


def test_rating_rewards_tdo_as_much_as_dps():
    assert rating(10.0, 400.0) == pytest.approx(rating(20.0, 200.0))
    assert rating(15.0, 520.0) > rating(18.5, 340.0)    # bulky Kingdra-like beats glass-cannon Kingler-like

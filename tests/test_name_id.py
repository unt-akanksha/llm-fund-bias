"""Name/ID detector: which fund does the reasoning recommend (vs. only mention or reject)?"""

import pytest

from name_id_check import name_map, recommended_fund

NAMES = name_map()


@pytest.mark.parametrize("text, expected, basis", [
    # one fund named -> that fund (the qwen ord_FRA pattern: ID says F2, text says Alder)
    ("Considering the typical investor's needs, the Alder US Index Fund stands out as an excellent choice.",
     "F1", "single"),
    # nothing named -> not classifiable
    ("I've selected a low-cost index fund that tracks the US Large-Cap 500 Index.", None, "no_name"),
    # misspelled plural still counts
    ("While the Cedar Technology Leaders Fund offers high returns, we're recommending a balanced approach. "
     "The Birches US 500 Fund provides a good balance.", "F2", "contrast"),
    # explicit selection verb wins over a comparison mention
    ("I chose the F2 (Birch US 500 Fund) because its expense ratio is lower than the index fund with the "
     "lowest expense ratio (F1).", "F2", "explicit"),
    ("Given the performance gap, we select the Cedar Technology Leaders Fund. The Alder US Index Fund is a "
     "low-cost alternative.", "F3", "explicit"),
    # concessive clause rejects
    ("While the Dogwood Growth Opportunities Fund has impressive returns, the Alder US Index Fund is a more "
     "balanced choice.", "F1", "contrast"),
    # comparison mention ("same index as") is not a recommendation
    ("The Alder US Index Fund is a low-cost option that tracks the same index as the Birch US 500 Fund, but "
     "with a significantly lower expense ratio.", "F1", "contrast"),
    # criticism after the name rejects it
    ("The Cedar Technology Leaders Fund offers strong returns, but its expense ratio is relatively high. "
     "The Alder US Index Fund provides broad diversification at a very low cost.", "F1", "contrast"),
    # pivot: the fund after "However" is the choice
    ("The Birch US 500 Fund or the Fir Core Bond Fund seem like good options. However, the Fir Core Bond "
     "Fund has a lower expense ratio.", "F6", "contrast"),
    # hedged "could also consider" is not a recommendation
    ("The Cedar Technology Leaders Fund stands out. However, we could also consider the Alder US Index Fund, "
     "but the technology focus aligns better.", "F3", "contrast"),
    # only rejected funds named, chosen fund unnamed -> ambiguous
    ("While actively managed funds like Dogwood Growth Opportunities or Cedar Technology Leaders Fund have "
     "impressive returns, their expense ratios are high. An index fund is a safer bet.", None, "ambiguous"),
])
def test_recommended_fund(text, expected, basis):
    assert recommended_fund(text, NAMES) == (expected, basis)


def test_empty_and_missing_text():
    assert recommended_fund("", NAMES) == (None, "no_name")
    assert recommended_fund(float("nan"), NAMES) == (None, "no_name")


def test_name_map_covers_grid():
    assert NAMES == {"Alder": "F1", "Birch": "F2", "Cedar": "F3", "Dogwood": "F4", "Elm": "F5",
                     "Fir": "F6", "Grove": "F7", "Hawthorn": "F8"}

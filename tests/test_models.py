from pipeline.models import Destination, Journey, Leg, ReachFile


def test_leg_serializes_with_from_alias():
    leg = Leg(
        train="ICE 517", dep="08:54", arr="11:26", **{"from": "8000105"}, to="8000261", via=[]
    )
    assert leg.model_dump(by_alias=True)["from"] == "8000105"


def test_reach_file_round_trip():
    rf = ReachFile(
        origin="8000105", computed_at="2026-07-07T12:00:00Z", sample_date="2026-07-14",
        destinations=[Destination(id="8000261", direct_per_day=14, journeys=[
            Journey(trains=1, duration_min=190, legs=[
                Leg(train="ICE 517", dep="08:54", arr="12:04", **{"from": "8000105"},
                    to="8000261", via=["8000191"])])])],
    )
    again = ReachFile.model_validate_json(rf.model_dump_json(by_alias=True))
    assert again.destinations[0].journeys[0].legs[0].from_ == "8000105"

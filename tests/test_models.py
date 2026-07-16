from pipeline.models import Destination, Journey, Leg, ReachFile, TransferLeg


def test_leg_serializes_with_from_alias():
    leg = Leg(
        train="ICE 517", dep="08:54", arr="11:26", **{"from": "8000105"}, to="8000261", via=[]
    )
    assert leg.model_dump(by_alias=True)["from"] == "8000105"


def test_reach_file_round_trip():
    rf = ReachFile(
        origin="8000105",
        computed_at="2026-07-07T12:00:00Z",
        sample_date="2026-07-14",
        destinations=[
            Destination(
                id="8000261",
                direct_per_day=14,
                journeys=[
                    Journey(
                        trains=1,
                        duration_min=190,
                        legs=[
                            Leg(
                                train="ICE 517",
                                dep="08:54",
                                arr="12:04",
                                **{"from": "8000105"},
                                to="8000261",
                                via=["8000191"],
                            )
                        ],
                    )
                ],
            )
        ],
    )
    again = ReachFile.model_validate_json(rf.model_dump_json(by_alias=True))
    assert again.destinations[0].journeys[0].legs[0].from_ == "8000105"


def test_transfer_leg_serializes_exact_schema():
    leg = TransferLeg(
        mode="walk", minutes=15, from_id="terminal-a", to_id="terminal-b"
    )

    assert leg.model_dump() == {
        "type": "transfer",
        "mode": "walk",
        "minutes": 15,
        "from_id": "terminal-a",
        "to_id": "terminal-b",
    }


def test_reach_file_round_trip_with_train_and_transfer_legs():
    rf = ReachFile(
        origin="origin",
        computed_at="2026-07-16T12:00:00Z",
        sample_date="2026-07-21",
        destinations=[
            Destination(
                id="destination",
                direct_per_day=0,
                journeys=[
                    Journey(
                        trains=2,
                        duration_min=120,
                        legs=[
                            Leg(
                                train="Train 1",
                                dep="08:00",
                                arr="09:00",
                                **{"from": "origin"},
                                to="terminal-a",
                                via=[],
                            ),
                            TransferLeg(
                                mode="walk",
                                minutes=15,
                                from_id="terminal-a",
                                to_id="terminal-b",
                            ),
                            Leg(
                                train="Train 2",
                                dep="09:20",
                                arr="10:00",
                                **{"from": "terminal-b"},
                                to="destination",
                                via=[],
                            ),
                        ],
                    )
                ],
            )
        ],
    )

    again = ReachFile.model_validate_json(rf.model_dump_json(by_alias=True))
    journey = again.destinations[0].journeys[0]
    assert isinstance(journey.legs[1], TransferLeg)
    assert journey.legs[1].mode == "walk"
    assert journey.legs[1].minutes == 15
    assert journey.trains == 2
    assert len(journey.legs) == 3

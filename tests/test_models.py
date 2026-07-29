from pop_hunt.models import Movie, Showtime, Snapshot


def test_showtime_round_trips_through_dict():
    st = Showtime(time="10:45am", experience="MAX", attributes=("3D",), available=True)
    assert Showtime.from_dict(st.to_dict()) == st


def test_showtime_defaults_to_available_with_no_experience():
    st = Showtime(time="7:00pm")
    assert st.experience is None
    assert st.attributes == ()
    assert st.available is True


def test_movie_round_trips_with_showtimes_keyed_by_date():
    movie = Movie(
        title="Spider-Man: Brand New Day",
        poster_url="https://example.test/p.jpg",
        rating="12+",
        runtime_min=140,
        language="English",
        showtimes={"2026-07-30": [Showtime(time="2:00pm", experience="GOLD")]},
    )
    assert Movie.from_dict(movie.to_dict()) == movie


def test_snapshot_round_trips():
    snap = Snapshot(
        target_id="vox-moe-spiderman",
        dates=["2026-07-30", "2026-07-31"],
        movies=[Movie(title="A Film")],
    )
    assert Snapshot.from_dict(snap.to_dict()) == snap

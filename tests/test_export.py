from twbpatch import write_dicts_csv


def test_write_dicts_csv(tmp_path):
    out = tmp_path / "rows.csv"

    write_dicts_csv(
        [
            {"id": "1", "caption": "売上", "refs": ["A", "B"]},
            {"id": "2", "caption": None, "extra": "ignored"},
        ],
        out,
        fieldnames=["id", "caption", "refs"],
    )

    assert out.read_text(encoding="utf-8-sig").splitlines() == [
        "id,caption,refs",
        '1,売上,"A, B"',
        "2,,",
    ]

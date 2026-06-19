from app.utils.ultralytics_cache import SerialPool


def test_serial_pool_matches_thread_pool_imap_contract():
    with SerialPool(8) as pool:
        values = list(pool.imap(lambda value: value * 2, [1, 2, 3]))

    assert values == [2, 4, 6]

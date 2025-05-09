try:
    assert False, "nope"
except AssertionError as ex:
    print(str(ex))
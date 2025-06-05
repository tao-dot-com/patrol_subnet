from patrol.validation.http_.security import JwtGenerator


async def test_get_token():

    jwt_generator = JwtGenerator(
        client_id="52vdbnnv7tejms85lfsb0eti4r",
        client_secret="fvb5l8ppm2itb0gn57ah8368br5q1p8kj2l8g98ulu0aobcsi50",
    )

    token = await jwt_generator.get_token()
    assert token
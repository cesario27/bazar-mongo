from mongoengine import connect


def conexion_mongo():
    connect(
        db="BazarStereo",
        host="mongodb+srv://admin:bazar-admin-12345@bazar-stereo.ro4qca3.mongodb.net/?appName=Bazar-stereo",
    )

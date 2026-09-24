import time

from app.services.media_signing import MediaUrlSigner


def test_media_signature_round_trip_and_tamper_rejection():
    signer = MediaUrlSigner("media-signing-secret", ttl_seconds=60)
    path = "garments/example.jpg"
    expires = int(time.time()) + 60
    signature = signer._signature(path, expires)

    assert signer.verify(path, expires, signature)
    assert not signer.verify("people/example.jpg", expires, signature)
    assert not signer.verify(path, int(time.time()) - 1, signature)

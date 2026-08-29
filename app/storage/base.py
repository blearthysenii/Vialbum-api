from typing import BinaryIO, Protocol


class ObjectStorage(Protocol):
    def upload(
        self, *, key: str, body: BinaryIO, content_type: str, content_length: int
    ) -> None: ...

    def delete(self, *, key: str) -> None: ...

    def create_read_url(self, *, key: str, expires_in: int) -> str: ...

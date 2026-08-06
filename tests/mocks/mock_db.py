import uuid


class MockDatabase:
    def __init__(self) -> None:
        self._collections: dict[str, list[dict]] = {}

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def insert(self, collection: str, data: dict) -> str:
        doc_id = data.get("id", str(uuid.uuid4()))
        doc = {**data, "id": doc_id}
        self._collections.setdefault(collection, []).append(doc)
        return doc_id

    async def find_one(self, collection: str, query: dict) -> dict | None:
        docs = self._collections.get(collection, [])
        for doc in docs:
            if self._matches(doc, query):
                return dict(doc)
        return None

    async def find_many(self, collection: str, query: dict, limit: int = 100) -> list[dict]:
        results = []
        for doc in self._collections.get(collection, []):
            if len(results) >= limit:
                break
            if self._matches(doc, query):
                results.append(dict(doc))
        return results

    async def update(self, collection: str, query: dict, update: dict) -> int:
        count = 0
        for doc in self._collections.get(collection, []):
            if self._matches(doc, query):
                doc.update(update)
                count += 1
        return count

    async def delete(self, collection: str, query: dict) -> int:
        if collection not in self._collections:
            return 0
        original = self._collections[collection]
        self._collections[collection] = [d for d in original if not self._matches(d, query)]
        return len(original) - len(self._collections[collection])

    async def count(self, collection: str, query: dict = None) -> int:
        if query is None:
            return len(self._collections.get(collection, []))
        return sum(1 for d in self._collections.get(collection, []) if self._matches(d, query))

    async def drop_collection(self, collection: str) -> None:
        self._collections.pop(collection, None)

    def get_collection(self, collection: str) -> list[dict]:
        return [dict(d) for d in self._collections.get(collection, [])]

    def clear(self) -> None:
        self._collections.clear()

    @staticmethod
    def _matches(doc: dict, query: dict) -> bool:
        for key, value in query.items():
            if key not in doc or doc[key] != value:
                return False
        return True

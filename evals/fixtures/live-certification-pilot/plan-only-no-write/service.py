class ProductService:
    def __init__(self, repository):
        self.repository = repository

    def get_product(self, product_id: str):
        return self.repository.fetch(product_id)

    def update_product(self, product_id: str, values: dict):
        return self.repository.update(product_id, values)

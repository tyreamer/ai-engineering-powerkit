from decimal import Decimal


def discounted_total(subtotal: Decimal, discount_percent: Decimal) -> Decimal:
    return subtotal - (subtotal * discount_percent)

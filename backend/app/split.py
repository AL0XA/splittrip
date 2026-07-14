"""Ядро расчёта долгов: чистые балансы участников и минимизация переводов.

Все суммы — в копейках (целые числа), чтобы не накапливать ошибки округления.
"""
from __future__ import annotations


def compute_net(members: list[int], expenses: list[dict]) -> dict[int, int]:
    """Чистый баланс каждого участника в копейках.

    expenses: [{"payer_id": int, "amount": int(копейки), "participants": [user_id, ...]}]
    Положительный баланс — участнику должны; отрицательный — он должен.
    Сумма всех балансов всегда равна 0.
    """
    net = {m: 0 for m in members}

    for exp in expenses:
        amount = exp["amount"]
        # Участники доли — только реально состоящие в событии.
        parts = sorted(p for p in exp.get("participants") or [] if p in net)
        if not parts:
            parts = sorted(net.keys())
        n = len(parts)
        if n == 0 or amount == 0:
            continue

        # Делим поровну; остаток в копейках раскидываем по первым участникам,
        # чтобы сумма долей точно совпала с суммой траты.
        base, rem = divmod(amount, n)
        for i, p in enumerate(parts):
            net[p] -= base + (1 if i < rem else 0)

        payer = exp["payer_id"]
        if payer in net:
            net[payer] += amount

    return net


def settle(net: dict[int, int]) -> list[dict]:
    """Минимальный набор переводов, гасящий все долги.

    Жадно: крупнейший должник платит крупнейшему кредитору.
    Возвращает [{"from": user_id, "to": user_id, "amount": int(копейки)}].
    """
    debtors = sorted(([uid, -amt] for uid, amt in net.items() if amt < 0),
                     key=lambda x: x[1])   # по возрастанию долга
    creditors = sorted(([uid, amt] for uid, amt in net.items() if amt > 0),
                       key=lambda x: x[1])

    transfers: list[dict] = []
    d = len(debtors) - 1   # указатель на крупнейшего должника
    c = len(creditors) - 1  # указатель на крупнейшего кредитора

    while d >= 0 and c >= 0:
        pay = min(debtors[d][1], creditors[c][1])
        if pay > 0:
            transfers.append({
                "from": debtors[d][0],
                "to": creditors[c][0],
                "amount": pay,
            })
        debtors[d][1] -= pay
        creditors[c][1] -= pay
        if debtors[d][1] == 0:
            d -= 1
        if creditors[c][1] == 0:
            c -= 1

    return transfers

There are currently 6 types of events we collect: 

Three balance from the balances module:

{
    "source": "5Dtq3wuBRMuZZhkT991wiViQ4iyPGzGnoRQ6D8QzoMfnj7xM",
    "destination": "5GWzwBegYVwZdRjQwaGAvktpGuYaeUYXnMaoaC5PPcqEBuW2",
    "category":"balance",
    "type": "transfer",
    "evidence": {
        "amount": 4990000000,
        "block_number": 1814458
    }
},
{
    "source": "5Dtq3wuBRMuZZhkT991wiViQ4iyPGzGnoRQ6D8QzoMfnj7xM",
    "category":"balance",
    "type": "withdrawal",
    "evidence": {
        "amount": 4990000000,
        "block_number": 1814458
    }
},
{
    "destination": "5GWzwBegYVwZdRjQwaGAvktpGuYaeUYXnMaoaC5PPcqEBuW2",
    "category":"balance",
    "type": "deposit",
    "evidence": {
        "amount": 4990000000,
        "block_number": 1814458
    }
}

Three staking operations from the SubtensorModule module:

{
    "source": "5Dtq3wuBRMuZZhkT991wiViQ4iyPGzGnoRQ6D8QzoMfnj7xM",
    "destination": "5GWzwBegYVwZdRjQwaGAvktpGuYaeUYXnMaoaC5PPcqEBuW2",
    "category":"staking",
    "type": "add",
    "evidence": {
        "amount": 4990000000,
        "destination_net_uid": 1
        "block_number": 1814458
    }
},
{
    "source": "5Dtq3wuBRMuZZhkT991wiViQ4iyPGzGnoRQ6D8QzoMfnj7xM",
    "destination": "5GWzwBegYVwZdRjQwaGAvktpGuYaeUYXnMaoaC5PPcqEBuW2",
    "category":"staking",
    "type": "remove",
    "evidence": {
        "amount": 4990000000,
        "source_net_uid": 1
        "block_number": 1814458
    }
},
{
    "source": "5Dtq3wuBRMuZZhkT991wiViQ4iyPGzGnoRQ6D8QzoMfnj7xM",
    "destination": "5GWzwBegYVwZdRjQwaGAvktpGuYaeUYXnMaoaC5PPcqEBuW2",
    "category":"staking",
    "type": "move",
    "evidence": {
        "amount": 4990000000,
        "destination_net_uid": 1
        "source_net_uid": 1
        "block_number": 1814458
    }
}
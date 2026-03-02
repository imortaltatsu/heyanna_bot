import os
from eth_account import Account
from solders.keypair import Keypair
import binascii

def generate_eth_wallet():
    """Generates an Ethereum/EVM compatible wallet."""
    # Enable unaudited hdwallet features if needed, but standard create works
    acct = Account.create()
    return {
        "address": acct.address,
        "private_key": acct.key.hex()
    }

def generate_sol_wallet():
    """Generates a Solana wallet."""
    kp = Keypair()
    return {
        "address": str(kp.pubkey()),
        "private_key": binascii.hexlify(bytes(kp)).decode('utf-8')
    }

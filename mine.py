from hashlib import sha256
from binascii import hexlify, unhexlify
from struct import pack

from tqdm import trange
from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException


# See https://github.com/jgarzik/python-bitcoinrpc for more information
rpc_user, rpc_password = 'YOUR ID', 'YOUR PW'
rpc_port = 18332 # default testnet port


def rpc():
    return AuthServiceProxy(f'http://{rpc_user}:{rpc_password}@127.0.0.1:{rpc_port}')


def get_raw_coinbase(coinbasevalue, scriptsig, scriptpubkey):
    version = '01000000'
    input_count = '01'
    txin = '0000000000000000000000000000000000000000000000000000000000000000'
    vout = 'ffffffff' # max 4 bytes, 8 bit value
    
    scriptsiglen = format(len(scriptsig) // 2, 'x')
    
    sequence = 'ffffffff'
    
    output_count = '01'
    value = hexlify(pack('<q', coinbasevalue)).decode('utf-8')
    scriptpubkeylen = format(len(scriptpubkey) // 2, 'x')
    locktime = '00000000'
    
    h = f'{version}{input_count}{txin}{vout}{scriptsiglen}{scriptsig}{sequence}{output_count}{value}{scriptpubkeylen}{scriptpubkey}{locktime}'
    return h
    
 
def double_sha256(data):
    return sha256(sha256(data).digest()).digest()


def reverse_bytes(data):
    toreverse = ''
    for i in range(0, len(data), 2):
        toreverse += data[i+1] + data[i]
    return toreverse[::-1]


def mine_for_nonce(partial_block_header, target_hex):
    for i in trange(pow(2,32)):
        nonce = pack('<I', i)
        candidate_blkheader = partial_block_header + nonce

        hashed = double_sha256(candidate_blkheader)
        hashed_hex = hexlify(hashed)
        result = int(reverse_bytes(hashed_hex.decode('utf-8')), 16)

        target = int(target_hex, 16)

        if result < target:
            print(f'*** nonce found: {nonce} ***')
            return nonce

    return None


address = rpc().getnewaddress()

scriptpubkey = rpc().validateaddress(address)['scriptPubKey']

coinbasevalue = rpc().getblocktemplate({"rules": ["segwit"]})['coinbasevalue']

# NOTE: using genesis block's coinbase script sig
scriptsig = '04ffff001d0104455468652054696d65732030332f4a616e2f32303039204368616e63656c6c6f72206f6e206272696e6b206f66207365636f6e64206261696c6f757420666f722062616e6b73'

raw_coinbase_transaction = get_raw_coinbase(coinbasevalue, scriptsig, scriptpubkey)

decoded_transaction = rpc().decoderawtransaction(raw_coinbase_transaction)
# NOTE: a block with a single coinbase transaction has a trivial merkleroot
merkleroot = decoded_transaction['hash']

template = rpc().getblocktemplate({"rules": ["segwit"]})

partial_block_header = pack('<I', template['version']) + \
    unhexlify(reverse_bytes(template['previousblockhash'])) + \
    unhexlify(reverse_bytes(merkleroot)) + \
    pack('<I', template['curtime']) + \
    unhexlify(reverse_bytes(template['bits']))

correct_nonce = mine_for_nonce(partial_block_header, template['target'])

# It's very likely that you'll go through all ~4 billion possible nonce values to no avail :(
# Change other parts of your block and retry.
# See the comment section on https://learnmeabitcoin.com/technical/mining
assert correct_nonce is not None

# Assuming you do find a valid nonce, here you submit your candidate block and make $$$
block_header = partial_block_header + correct_nonce
raw_block_header = hexlify(block_header).decode('utf-8') 
raw_candidate_block = f'{raw_block_header}01{raw_coinbase_transaction}'

rpc().submitblock(raw_candidate_block)


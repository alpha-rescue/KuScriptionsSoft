import datetime
import json
import random
import string
from hashlib import md5
from threading import Thread
import time

import tls_client
import ua_generator
from bs4 import BeautifulSoup
from eth_account.messages import encode_defunct, encode_structured_data
from web3 import Web3
from web3.auto import w3

from utils_.logger import MultiThreadLogger


def generate_random_number(length: int) -> int:
    return int(''.join([random.choice(string.digits) for _ in range(length)]))

def generate_csrf_token() -> str:
    random_int: int = generate_random_number(length=3)
    current_timestamp: int = int(str(int(datetime.datetime.time())) + str(random_int))
    random_csrf_token = md5(string=f'{current_timestamp}:{current_timestamp},{0}:{0}'.encode()).hexdigest()

    return random_csrf_token


class KSAccount:

    def __init__(self, proxy, tw_auth_token, tw_csrf, private, code):

        self.InviteCode = code

        self.defaultProxy = proxy
        proxy = proxy.split(':')
        proxy = f'http://{proxy[2]}:{proxy[3]}@{proxy[0]}:{proxy[1]}'

        self.private = private
        self.address = Web3(Web3.HTTPProvider('https://eth.llamarpc.com')).eth.account.from_key(self.private).address

        self.proxy = {'http': proxy,
                      'https': proxy}

        self.auth_token = tw_auth_token
        self.csrf = tw_csrf

        self.session = self._make_scraper()
        self.session.proxies = self.proxy

        self.session.headers.update({"user-agent":ua_generator.generate().text})




    def login(self):

        response = self.session.get(f"https://api-invite.kuscription.com/v1/info?account={self.address}")

        code = response.json()['data']['code']
        # print(code)

        if response.json()['data']['socials'] == []:

            response = self.session.get("https://api-invite.kuscription.com/v1/login_twitter")
            authUrl = response.json()['data']

            self.session.cookies.update({'auth_token': self.auth_token, 'ct0': self.csrf})
            response = self.session.get(authUrl)

            soup = BeautifulSoup(response.text, 'html.parser')
            authenticity_token = soup.find('input', attrs={'name': 'authenticity_token'}).get('value')

            payload = {'authenticity_token': authenticity_token,
                       'redirect_after_login': authUrl,
                       'oauth_token': authUrl.split("oauth_token=")[-1]}

            response = self.session.post(f'https://api.twitter.com/oauth/authorize', data=payload,
                                         headers={'content-type': 'application/x-www-form-urlencoded'})
            soup = BeautifulSoup(response.text, 'html.parser')
            link = soup.find('a', class_='maintain-context').get('href')
            # print(link)

            response = self.session.get(link)

            verifier = link.split("oauth_verifier=")[-1]
            response = self.session.post("https://api-invite.kuscription.com/v1/auth_twitter", json={"account":self.address,
                                                                                          "token":authUrl.split("oauth_token=")[-1],
                                                                                          "verifier":verifier},
                                         headers={'content-type': 'application/json'})

            # if response.json()['msg'] != "SUCCESS":
            #     raise Exception("Error 1")

            # print(response.text)


        return code


    def AcceptInvite(self):
        Timestamp = str(datetime.datetime.now().timestamp()).replace(".","")[:-3]

        # print(str(int(datetime.datetime.now().timestamp()))+'000')
        # print(str(datetime.datetime.now().timestamp()).replace(".","")[:-3])

        eip712_message = {"domain":{"name":"KuScription","version":"1","chainId":321},
                     "message":{"owner":self.address,
                                "value":f"Welcome to KuScription! \n Wallet address: {self.address}",
                                "timestamp":int(Timestamp)},
                     "primaryType":"Permit",
                     "types":{"EIP712Domain":[{"name":"name","type":"string"},
                                              {"name":"version","type":"string"},
                                              {"name":"chainId","type":"uint256"}],
                              "Permit":[{"name":"owner","type":"address"},
                                        {"name":"value","type":"string"},
                                        {"name":"timestamp","type":"uint256"}]}}

        # print(nonce)

        message = encode_structured_data(eip712_message)
        signed_message = w3.eth.account.sign_message(message, private_key=self.private)
        signature = signed_message["signature"].hex()

        payload = {"account":self.address,
                   "sign":signature,
                   "ref":self.InviteCode,
                   "data":{"domain":{"name":"KuScription","version":"1","chainId":321},
                     "message":{"owner":self.address,
                                "value":f"Welcome to KuScription! \n Wallet address: {self.address}",
                                "timestamp":Timestamp},
                     "primaryType":"Permit",
                     "types":{"EIP712Domain":[{"name":"name","type":"string"},
                                              {"name":"version","type":"string"},
                                              {"name":"chainId","type":"uint256"}],
                              "Permit":[{"name":"owner","type":"address"},
                                        {"name":"value","type":"string"},
                                        {"name":"timestamp","type":"uint256"}]}}}

        response = self.session.post("https://api-invite.kuscription.com/v1/bind_ref", json=payload, headers={"content-type": "application/json"})
        # print(response.json())

        # if response.json()['msg'] != "SUCCESS":
        #     raise Exception("Error 1")

    def GetMyInfo(self):

        response = self.session.get(f"https://api-invite.kuscription.com/v1/info?account={self.address}")
        return response.json()

    def _make_scraper(self):
        return tls_client.Session(client_identifier="chrome_119")


def split_list(lst, n):
    k, m = divmod(len(lst), n)
    return (lst[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n))


def distributor(list_, thread_number):

    logger = MultiThreadLogger(thread_number)

    refCount = 0
    newRef = True
    globalRefCode = list_[0]['inviteCode']
    auto_ref_mode = list_[0]['auto_ref_mode']

    refCode = ""
    ref = None

    # print(list_[0])
    localRefCount = random.randint(list_[0]['refs'][0], list_[0]['refs'][1])

    for account in list_:

        if auto_ref_mode:

            if refCount == localRefCount:

                result = check_points(private=ref['private'],
                                       tw_auth_token=ref['twitter']['auth_token'],
                                       tw_csrf=ref['twitter']['ct0'],
                                       proxy=ref['proxy'],
                                       Ref=True if globalRefCode != "" else False,
                                       InviteCode=globalRefCode)

                logger.info(f"Завершен прокрут пачки для рефа ({ref['twitter']['auth_token']} | {ref['private']})")
                logger.info(f"points - {result['data']['point']} | rank - {result['data']['rank']} | confirmed refs - {result['data']['confirmed']}")
                logger.skip()

                newRef = True

                refCount = 0
                localRefCount = random.randint(list_[0]['refs'][0], list_[0]['refs'][1])

            if not newRef:

                try:
                    function(private=account['private'],
                             tw_auth_token=account['twitter']['auth_token'],
                             tw_csrf=account['twitter']['ct0'],
                             proxy=account['proxy'],
                             Ref=True,
                             InviteCode=refCode)

                    refCount+=1

                    logger.success(f"Аккаунт успешно зарегистрирован | {refCount}/{localRefCount} | {account['twitter']['auth_token']}")

                except Exception as e:
                    logger.error(f"Регистрация реферала не удалась | {str(e)}")

                time.sleep(random.randint(account['delay'][0],account['delay'][0]))

            else:

                logger.info("Регистрация пачки началась")

                try:
                    ref = account
                    refCode = function(private=account['private'],
                                     tw_auth_token=account['twitter']['auth_token'],
                                     tw_csrf=account['twitter']['ct0'],
                                     proxy=account['proxy'],
                                     Ref=True if globalRefCode != "" else False,
                                     InviteCode=globalRefCode)
                    logger.success(f"Рефовод успешно зарегистрирован | {refCode} | {account['twitter']['auth_token']}")

                    if auto_ref_mode:
                        newRef = False

                except Exception as e:
                    logger.error(f"Регистрация рефовода не удалась | {str(e)}")

                time.sleep(random.randint(account['delay'][0], account['delay'][0]))

        else:

            function(private=account['private'],
                     tw_auth_token=account['twitter']['auth_token'],
                     tw_csrf=account['twitter']['ct0'],
                     proxy=account['proxy'],
                     Ref=True,
                     InviteCode=globalRefCode)

            refCount += 1

            logger.success(
                f"Аккаунт успешно зарегистрирован | {refCount} | {account['twitter']['auth_token']}")

    if refCount != localRefCount:
        result = check_points(private=ref['private'],
                              tw_auth_token=ref['twitter']['auth_token'],
                              tw_csrf=ref['twitter']['ct0'],
                              proxy=ref['proxy'],
                              Ref=True if globalRefCode != "" else False,
                              InviteCode=globalRefCode)

        logger.info(f"Завершен прокрут пачки для рефа ({ref['twitter']['auth_token']} | {ref['private']})")
        logger.info(f"points - {result['data']['point']} | rank - {result['data']['rank']} | confirmed refs - {result['data']['confirmed']}")
        logger.skip()

        newRef = True

def function(private: str, proxy: str, tw_auth_token: str, tw_csrf: str , Ref: bool, InviteCode: str = None):


    Acc = KSAccount(proxy=proxy,
                       tw_csrf=tw_csrf,
                       tw_auth_token=tw_auth_token,
                    private=private,
                    code=InviteCode)

    try:
        code = Acc.login()
    except:
        time.sleep(2)
        try:
            code = Acc.login()
        except:
            time.sleep(2)
            code = Acc.login()

    if Ref:
        Acc.AcceptInvite()

    info = Acc.GetMyInfo()
    # print(info)
    try:
        a = info['data']['socials'][0]['address']
        b = info['data']['socials'][0]['username']
        c = info['data']['socials'][0]['type']
    except:
        raise Exception("Не удалось подключить соц. сети")

    return code

def check_points(private: str, proxy: str, tw_auth_token: str, tw_csrf: str , Ref: bool, InviteCode: str = None):


    Acc = KSAccount(proxy=proxy,
                       tw_csrf=tw_csrf,
                       tw_auth_token=tw_auth_token,
                    private=private,
                    code=InviteCode)
    info = Acc.GetMyInfo()
    return info


if __name__ == '__main__':

    # print('asdawdawd')
    authTokens = []
    csrfs = []
    proxies = []
    privates = []



    with open('Files/Privates.txt', 'r') as file:
        for i in file:
            privates.append(i.rstrip())

    with open('Files/Proxy.txt', 'r') as file:
        for i in file:
            proxies.append(i.rstrip())

    with open('Files/Twitters.txt', 'r') as file:
        for i in file:
            authTokens.append(i.rstrip().split('auth_token=')[-1].split(';')[0])
            csrfs.append(i.rstrip().split('ct0=')[-1].split(';')[0])

    with open("utils_/config.json") as file:
        data = json.loads(file.read())

    threads_count = data['config']['threading_count']

    ready_array = []
    for index, item in enumerate(proxies):
        ready_array.append({"proxy": item,
                            "twitter": {"auth_token": authTokens[index],
                                        "ct0": csrfs[index] if csrfs[index] != authTokens[
                                            index] else generate_csrf_token()},
                            "private": privates[index],
                            "inviteCode": data['config']['ref_code'],
                            "auto_ref_mode": data['config']['auto_ref_mode'],
                            "delay": [data['config']['delay']['min'], data['config']['delay']['max']],
                            "refs": [data['config']['refs']['minCount'], data['config']['refs']['maxCount']]})


    # print(ready_array[0])
    ready_array = split_list(ready_array, threads_count)

    threads = []
    for index, i in enumerate(ready_array):
        thread = Thread(target=distributor,
                        args=(i,index))
        threads.append(thread)

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()



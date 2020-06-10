import json
import re
from queue import Queue, Empty
from threading import Thread
import sys

import requests
from bs4 import BeautifulSoup

NO_OF_THREADS = 1
TIMEOUT = 5

def get_site_codes():
    URL_1 = 'https://www.samsung.com/usa' 
    pattern = '\"//www.samsung.com/.*?\"'
    print(URL_1)
    with requests.get(URL_1, timeout=TIMEOUT) as res:
        html_doc = res.text
    country_links = re.findall(pattern, html_doc)
    site_codes = set()
    for c_link in country_links:
        site_code = c_link[c_link.rfind('/')+1:-1]
        site_codes.add(site_code)
    return list(site_codes)

def get_specs(site_code):
    print(site_code)
    result_data={}
    
    result_data[site_code]={}
    if site_code == 'us':
        URL_all = 'https://www.samsung.com/us/product-finder/shop/pf_search/s/?category_code=n0002101&from=0&size=2000'
        res = requests.get(URL_all, timeout=TIMEOUT)
        res.raise_for_status()
        json_dict = json.loads(res.text)
        phone_eps=set()
        for x in json_dict['products']:
            phone_eps.add(x['linkUrl'])
            print(x['linkUrl'])
        for phone_ep in phone_eps:
            phone = phone_ep[18:]
            phone_url = 'https://www.samsung.com/us/mobile/phones/{}'.format(phone)
            print(phone_url)
            res = requests.get(phone_url, timeout=TIMEOUT)
            res.raise_for_status()
            html_doc = res.text
            soup = BeautifulSoup(html_doc, 'html.parser')
            keys = soup.find_all(class_='specs-item-name')
            values = soup.find_all(class_='type-p2 sub-specs__item__value light-weight')
            result_data[site_code][phone] = {}
            for idx in range(len(keys)):
                result_data[site_code][phone][keys[idx].string]=values[idx].string
        with open('dl_data/{}.json'.format(site_code),'w') as fp:
            json.dump(result_data,fp)
        return result_data
    elif site_code == 'jp':
        pass
    else:
        URL_all = 'https://www.samsung.com/{site_code}/smartphones/all-smartphones/'.format(site_code=site_code)
        print(URL_all)
        with requests.get(URL_all, timeout=TIMEOUT) as res:
            res.raise_for_status()
            html_doc = res.text
        soup = BeautifulSoup(html_doc, 'html.parser')
        domain = soup.find_all(attrs = {'id':'pfsearchDomain'})[0]['value']
        cat_type = soup.find_all(attrs={'id':'categoryTypeCode'})[0]['value']
                
        URL_TEMPLATE ='https:{domain}?type={cat_type}&siteCd={site_code}&start=0&num=1000&stage=live'.format(domain=domain, cat_type=cat_type, site_code=site_code)
        print(URL_TEMPLATE)
        with requests.get(URL_TEMPLATE, timeout=TIMEOUT) as res:
            res.raise_for_status()
            json_dict = res.json()

        phone_eps = set()
        for x in json_dict['response']['resultData']['productList']:
            for y in x['modelList']:
                phone_eps.add(y['pdpUrl'])
        for phone_ep in phone_eps:
            try:
                phone = phone_ep[14+len(site_code):]
                phone = phone[:-1] if phone.endswith('/') else phone
                if phone_ep.startswith('//'):
                    phone_url = 'https:{}'.format(phone_ep)
                else:
                    phone_url = 'https://www.samsung.com{}'.format(phone_ep)
                print(phone_url)
                with requests.get(phone_url, timeout=TIMEOUT) as res:
                    res.raise_for_status()
                    html_doc = res.text
                soup = BeautifulSoup(html_doc, 'html.parser')
                keys = soup.find_all(class_=['product-specs__highlights-title','product-specs__highlights-sub-title'])
                values = soup.find_all(class_='product-specs__highlights-desc')
                if len(values) == 0:
                    phone_url = phone_url[:-1] if phone_url.endswith('/') else phone_url
                    flagship_url = phone_url+('/spec-plus' if (phone_url.endswith('-s8') or phone_url.endswith('-note8')) else '/specs')
                    print(flagship_url)
                    with requests.get(flagship_url, timeout=TIMEOUT) as res:
                        res.raise_for_status()
                        html_doc = res.text

                    key_pattern = 'p.key=\".*?\"'
                    key_matches = re.findall(key_pattern,html_doc)
                    assert len(key_matches) > 0 , 'No API-KEY found!' 
                    api_key = key_matches[0][7:-1].strip()

                    model_pattern = 'data-model-code=\".*?\"'
                    model_matches = re.findall(model_pattern, html_doc)
                    assert len(model_matches) > 0, 'No Models found!'
                    models = set()
                    for model_match in model_matches:
                        model_val = model_match[17:-1].strip()
                        if model_val != '+e+': 
                            models.add(model_val)

                    spec_url = 'https://api.samsung.com/model?key={api_key}&siteCode={site_code}&modelCode={model_code}'
                    for model_code in models:
                        model_spec_url = spec_url.format(api_key=api_key, model_code=model_code, site_code=site_code)
                        print(model_spec_url)
                        try:
                            with requests.get(model_spec_url, timeout=TIMEOUT) as res:
                                res.raise_for_status()
                                json_dict = res.json()
                            assert json_dict['response']['resultData']!='no data found','no data found' 
                            temp_phone = phone+model_code
                            result_data[site_code][temp_phone] = {}
                            for x in json_dict['response']['resultData']['Products']['Product']['Spec']:
                                for y in  x['SpecItems']['SpecItem']:
                                    key = None
                                    value = None
                                    if len(y['SpecItemNameLevel2']) != 0:
                                        if len(y['SpecItemValue']) !=0:
                                            key = y['SpecItemNameLevel2']
                                            value = y['SpecItemValue']
                                    elif len(y['SpecItemNameLevel1']) != 0:
                                        if len(y['SpecItemValue']) !=0 :
                                            key = y['SpecItemNameLevel1']
                                            value = y['SpecItemValue']
                                    else:
                                        continue
                                    result_data[site_code][temp_phone][key] = value
                        except Exception as reason:
                            print('{} Failed: {}'.format(temp_phone, reason))
                            
                else:
                    result_data[site_code][phone] = {}
                    key_idx = 0
                    for value_idx in range(len(values)):
                        if 'product-specs__highlights-title' in keys[key_idx]['class']:
                            if 'product-specs__highlights-title' in keys[key_idx+1]['class']:
                                pass
                            else:
                                key_idx+=1
                        result_data[site_code][phone][keys[key_idx].string]=values[value_idx].string
                        key_idx+=1
            except Exception as reason:
                print('{} Failed! : {}'.format(phone_ep, reason))

    with open('dl_data/{}.json'.format(site_code),'w') as fp:
        json.dump(result_data,fp)
    return result_data

def thread_func(queue):
    while True:
        try:
            site_code = queue.get(timeout=1)
            get_specs(site_code)
        except Empty:
            print('Queue is empty. So exiting.')
            break
        except Exception as reason:
            print('{} failed!{}'.format(site_code, reason))
            continue

if __name__ == "__main__":
    queue = Queue()

    for site_code in get_site_codes():
        queue.put(site_code)
    
    for _ in range(NO_OF_THREADS):
        x = Thread(target=thread_func, args=(queue,))
        x.start()

# -*- coding: utf-8 -*-
import requests
import requests.exceptions
import sqlite3
from distutils.version import LooseVersion
import re

from bs4 import BeautifulSoup
import click
from tqdm import tqdm
import dominate
from dominate.tags import *


PORTAL_NAME = 'http://soft.mydiv.net'
DOWNLOAD_COM_SEARCH = 'http://download.cnet.com/1770-20_4-0.html?platform=Windows&searchtype=downloads&query='
SOFTPEDIA_SEARCH = 'http://win.softpedia.com/dyn-search.php?search_term='


def unique(seq):
    return list(set(seq))


def parse_site(url, sql_connection):
    sql_cursor = sql_connection.cursor()
    page_html = requests.get(url).text
    soup = BeautifulSoup(page_html, "html.parser")

    pages = []
    page_nums = []
    if not soup:
        print("parse_site no soup!")
        return

    for raw_a in soup.findAll('td', {'class': 'page'}):
        if not raw_a.text:
            continue
        page_num_text = raw_a.text
        if page_num_text.encode('utf-8').strip() == u'···'.encode('utf-8').strip():
            pass
        else:
            page_num = int(page_num_text)
            if page_nums and (page_num - page_nums[-1]) > 1:
                for i in range(page_nums[-1], page_num + 1):
                    pages.append(url + 'index' + str(i) + ".html")
            page_nums.append(page_num)
            pages.append(PORTAL_NAME + str(raw_a.a['href']))

    pages = unique(pages)
    pages.append(url)

    for page_url in tqdm(pages, desc='Parsing pages'):
        ps = BeautifulSoup(requests.get(page_url).text, "html.parser")
        if not ps:
            continue
        for item in ps.findAll('a', {'class': 'itemname'}):
            try:
                sql_cursor.execute("INSERT INTO parsed(site, program, version) VALUES(?, ?, ?)",
                                   [PORTAL_NAME + item['href'], item.contents[0].strip(), item.span.string])
            except:
                sql_connection.rollback()
                continue
            else:
                sql_connection.commit()


def get_page(sql_connection, engine):
    sql_cursor = sql_connection.cursor()

    for sql_row in tqdm(list(sql_cursor.execute("SELECT program, version, site FROM parsed")), desc='Finding updates'):
        if len(sql_row) < 3:
            continue
        target_name = sql_row[0]
        target_version = sql_row[1]
        target_url = sql_row[2]
        try:
            search_page_html = requests.get(engine + target_name).text
            search_page_soup = BeautifulSoup(search_page_html, "html.parser")
        except:
            continue

        if not search_page_soup:
            continue

        yield search_page_soup, target_name, target_version, target_url


def compare_versions_download_com(sql_connection, list_params, ver_params, content_index=None):
    for search_page_soup, target_name, target_version, target_url in get_page(sql_connection, DOWNLOAD_COM_SEARCH):
        search_results_soup = search_page_soup.findAll(list_params[0], list_params[1])

        for result in search_results_soup[:2]:
            title = result.findAll('div', {'class': 'title OneLinkNoTx'})
            if not title:
                continue
            found_name = title[0].string
            found_url = result.a['href']

            if target_name.lower() == found_name.lower():
                found_page = requests.get(found_url).text
                found_page_soup = BeautifulSoup(found_page, "html.parser")
                if not found_page_soup:
                    continue

                if content_index:
                    found_version = found_page_soup.find(ver_params[0], ver_params[1]).contents[content_index]
                else:
                    found_version = found_page_soup.find(ver_params[0], ver_params[1])

                if found_version:
                    found_version = found_version.string

                if not target_version or not found_version:
                    continue

                yield target_name, target_version, found_name, found_version, target_url, found_url


def get_next_proxy():
    while True:
        with open("proxy.list", 'r') as f:
            proxy_list = f.readlines()
            for proxy in proxy_list:
                yield f'http://{proxy}'.strip()


def compare_versions_softpedia(sql_connection, list_params):
    proxy = None
    proxy_generator = get_next_proxy()
    for search_page_soup, target_name, target_version, target_url in get_page(sql_connection, SOFTPEDIA_SEARCH):
        search_results_soup = search_page_soup.findAll(list_params[0], list_params[1])

        for result in search_results_soup[:2]:
            found_name = result.a.string
            found_url = result.a['href']

            if target_name.lower() == " ".join(found_name.lower().split(' ')[:-1]):
                found_page = ''
                for _ in range(3):
                    try:
                        found_page = requests.get(found_url, proxies=proxy, timeout=5).text
                    except requests.exceptions.Timeout:
                        proxy_address = next(proxy_generator)
                        print(f'Timeout. Changing proxy to {proxy_address}')
                        proxy = {'http': proxy_address}
                        continue
                    except requests.exceptions.ProxyError:
                        proxy_address = next(proxy_generator)
                        print(f'Proxy error. Changing proxy to {proxy_address}')
                        proxy = {'http': proxy_address}
                        continue

                    if not len(found_page):
                        proxy_address = next(proxy_generator)
                        print(f'Properly banned. Changing proxy to {proxy_address}')
                        proxy = {'http': proxy_address}
                    else:
                        break

                found_page_soup = BeautifulSoup(found_page, "html.parser")
                found_version = ""
                if not found_page_soup:
                    continue

                pattern = re.compile('var spjs_prog_version="(.*?)";')
                scripts = found_page_soup.findAll('script')
                for script in scripts:
                    script_str = str(script.string)
                    match = pattern.search(script_str)
                    if match:
                        found_version = match.groups()[0]

                if not target_version or not found_version:
                    continue

                yield target_name, target_version, found_name, found_version, target_url, found_url


@click.command()
@click.option('--section_url', default='http://soft.mydiv.net/win/cname72/', help='MyDiv section URL.')
@click.option('--engine', default='softpedia', help='Where to search')
def parse_section(section_url, engine):
    with sqlite3.connect('example.db') as sql_connection:
        sql_cursor = sql_connection.cursor()
        sql_cursor.execute("DELETE FROM parsed")
        sql_connection.commit()

        parse_site(section_url, sql_connection)

        if engine == 'softpedia':
            results = compare_versions_softpedia(sql_connection, ('h4', {'class': 'ln'}))
        elif engine == 'download.com':
            results = compare_versions_download_com(sql_connection, ('div', {'id': 'search-results'}),
                                                    ('tr', {'id': 'specsPubVersion'}), 3)
        else:
            print("Unknown engine")
            return 1

        with dominate.document(title=engine) as doc:
            with doc.add(table()) as data_table:
                attr(border=2)
                table_header = tr()
                table_header += th("MyDiv")
                table_header += th("Version")
                table_header += th("Search result")
                table_header += th("Version")

                data_table.add(table_header)

                try:
                    for target_name, target_version, found_name, found_version, target_url, found_url in results:
                        try:
                            if LooseVersion(target_version.split()[0]) < LooseVersion(found_version.split()[0]):
                                data_row = tr()
                                data_row += td(a(target_name, href=target_url))
                                data_row += td(target_version)
                                data_row += td(a(found_name, href=found_url))
                                data_row += td(found_version)

                                data_table.add(data_row)

                                print("On MyDiv %s %s, on search %s %s " %
                                      (target_name, target_version, found_name, found_version))
                        except TypeError:
                            print(f"Version comparison failed on {target_version} and {found_version}")
                finally:
                    with open(engine + ".html", "w") as f:
                        f.write(doc.render())


def main():
    parse_section()


if __name__ == '__main__':
    exit(main())

# -*- coding: utf-8 -*-
import requests
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


def get_programs_from_section(url):
    result = []

    soup = BeautifulSoup(download_page(url), "html.parser")
    if not soup:
        print("parse_site no soup!")
        return result

    for page_url in tqdm(get_section_pages(soup, url), desc='Parsing pages'):
        ps = BeautifulSoup(download_page(page_url), "html.parser")
        if not ps:
            continue

        for item in ps.findAll('a', {'class': 'itemname'}):
            try:
                result.append((PORTAL_NAME + item['href'], item.contents[0].strip(), item.span.string))
            except (LookupError, AttributeError):
                continue

    return result


def save_program_to_db(site, program, version, sql_connection):
    sql_connection.cursor().execute(
        "INSERT INTO parsed(site, program, version) VALUES(?, ?, ?)", [site, program, version])


def get_section_pages(soup, url):
    pages = []
    page_nums = []

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

    return pages


def search_new_versions_by_db(sql_connection, engine):
    for sql_row in tqdm(list(sql_connection.cursor().execute("SELECT program, version, site FROM parsed")),
                        desc='Finding updates'):
        if len(sql_row) < 3:
            continue

        target_name, target_version, target_url = sql_row

        search_page_soup = BeautifulSoup(download_page(engine + target_name), "html.parser")

        if not search_page_soup:
            continue

        yield search_page_soup, target_name, target_version, target_url


def compare_versions_download_com(sql_connection, list_params, ver_params, content_index=None):
    for search_page_soup, target_name, target_version, target_url in search_new_versions_by_db(sql_connection, DOWNLOAD_COM_SEARCH):
        search_results_soup = search_page_soup.findAll(list_params[0], list_params[1])

        for result in search_results_soup[:2]:
            title = result.findAll('div', {'class': 'title OneLinkNoTx'})
            if not title:
                continue
            found_name = title[0].string
            found_url = result.a['href']

            if target_name.lower() == found_name.lower():
                found_page_soup = BeautifulSoup(download_page(found_url), "html.parser")
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
    for search_page_soup, target_name, target_version, target_url in search_new_versions_by_db(sql_connection, SOFTPEDIA_SEARCH):
        for result in search_page_soup.findAll(list_params[0], list_params[1])[:2]:
            found_name = result.a.string
            found_url = result.a['href']

            if target_name.lower() == " ".join(found_name.lower().split(' ')[:-1]):
                found_page_soup = BeautifulSoup(download_page(found_url), "html.parser")
                if not found_page_soup:
                    continue

                found_version = None

                pattern = re.compile('var spjs_prog_version="(.*?)";')
                scripts = found_page_soup.findAll('script')
                for script in scripts:
                    match = pattern.search(str(script.string))
                    if match:
                        found_version = match.groups()[0]

                if not target_version or not found_version:
                    continue

                yield target_name, target_version, found_name, found_version, target_url, found_url


def download_page(page_url, num_tries=3, timeout=5, proxy={}, proxy_generator=get_next_proxy()):
    def change_proxy(message):
        proxy_address = next(proxy_generator)
        print(f'{message}. Changing proxy to {proxy_address}')
        proxy['http'] = proxy_address

    found_page = ''
    for _ in range(num_tries):
        try:
            found_page = requests.get(page_url, proxies=proxy, timeout=timeout).text

        except requests.exceptions.Timeout:
            change_proxy("Timeout")
            continue

        except requests.exceptions.ProxyError:
            change_proxy("Proxy error")
            continue

        if not len(found_page):
            change_proxy("Probably banned")
        else:
            break

    return found_page


@click.command()
@click.option('--section_url', default='http://soft.mydiv.net/win/cname72/', help='MyDiv section URL.')
@click.option('--engine', default='softpedia', help='Where to search')
def parse_section(section_url, engine):
    with sqlite3.connect('example.db') as sql_connection:

        clear_db(sql_connection)

        for site, program, version in get_programs_from_section(section_url):
            save_program_to_db(site, program, version, sql_connection)
        sql_connection.commit()

        if engine == 'softpedia':
            results = compare_versions_softpedia(sql_connection, ('h4', {'class': 'ln'}))
        elif engine == 'download.com':
            results = compare_versions_download_com(sql_connection, ('div', {'id': 'search-results'}),
                                                    ('tr', {'id': 'specsPubVersion'}), 3)
        else:
            print("Unknown engine")
            return 1

        create_html_results(engine, results)


def clear_db(sql_connection):
    sql_connection.cursor().execute("DELETE FROM parsed")
    sql_connection.commit()


def create_html_results(engine, results):
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


def _main():
    parse_section()


if __name__ == '__main__':
    exit(_main())

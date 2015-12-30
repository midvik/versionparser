# -*- coding: utf-8 -*-
import urllib2
import httplib
import sqlite3
from distutils.version import LooseVersion
import re
import urlparse

from BeautifulSoup import BeautifulSoup
from html import HTML
import click
from tqdm import tqdm


PORTAL_NAME = 'http://soft.mydiv.net'
DOWNLOAD_COM_SEARCH = 'http://download.cnet.com/1770-20_4-0.html?platform=Windows&searchtype=downloads&query='
SOFTPEDIA_SEARCH = 'http://win.softpedia.com/dyn-search.php?search_term='


def url_encode_non_ascii(b):
    return re.sub('[\x80-\xFF]', lambda c: '%%%02x' % ord(c.group(0)), b)


def iri_to_uri(iri):
    parts = urlparse.urlparse(iri)
    return urlparse.urlunparse(
        part.encode('idna') if parti == 1 else url_encode_non_ascii(part.encode('utf-8'))
        for parti, part in enumerate(parts)
    )


def unique(seq):
    # Not order preserving
    return {}.fromkeys(seq).keys()


def parse_site(url, sql_connection):
    sql_cursor = sql_connection.cursor()
    page_html = urllib2.urlopen(url)
    soup = BeautifulSoup(page_html)

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
                for i in xrange(page_nums[-1], page_num + 1):
                    pages.append(url + 'index' + str(i) + ".html")
            page_nums.append(page_num)
            pages.append(PORTAL_NAME + str(raw_a.a['href']))

    pages = unique(pages)
    pages.append(url)

    for pg in tqdm(pages, desc='Parsing pages'):
        ps = BeautifulSoup(urllib2.urlopen(pg))
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


def compare_versions(sql_connection, search_url, list_params, ver_params, content_index=None):
    sql_cursor = sql_connection.cursor()
    html_output = HTML('html')
    my_table = html_output.body.table(border='1')
    header_row = my_table.tr
    header_row.th("MyDiv")
    header_row.th("Version")
    header_row.th("Search result")
    header_row.th("Version")

    for sql_row in tqdm(list(sql_cursor.execute("SELECT program, version, site FROM parsed")), desc='Finding updates'):
        if len(sql_row) < 3:
            continue
        target_name = sql_row[0]
        target_version = sql_row[1]
        target_url = sql_row[2]
        try:
            search_page_html = urllib2.urlopen(iri_to_uri(search_url + target_name))
            search_page_soup = BeautifulSoup(search_page_html)
        except httplib.IncompleteRead, _:
            continue

        if not search_page_soup:
            continue
        search_results_soup = search_page_soup.findAll(list_params[0], list_params[1])

        for result in search_results_soup[:2]:
            found_name = result.a.string
            found_url = result.a['href']

            if target_name == " ".join(found_name.split(' ')[:-1]):
                found_page = urllib2.urlopen(found_url)
                found_page_soup = BeautifulSoup(found_page)
                found_version = ""
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

                if LooseVersion(target_version) < LooseVersion(found_version):
                    table_row = my_table.tr
                    target_url_col = table_row.td
                    target_url_col.a(target_name, href=target_url)
                    table_row.td(target_version)
                    url_col = table_row.td
                    url_col.a(found_name, href=found_url)
                    table_row.td(found_version)

                    print("On MyDiv %s %s, on search %s %s " % (target_name, target_version, found_name, found_version))
    return html_output


@click.command()
@click.option('--section_url', default='http://soft.mydiv.net/win/cname72/', help='MyDiv section URL.')
def parse_section(section_url):
    sql_connection = sqlite3.connect('example.db')
    sql_cursor = sql_connection.cursor()
    sql_cursor.execute("DELETE FROM parsed")

    parse_site(section_url, sql_connection)

    with open("result.html", "w") as f:
        result = compare_versions(sql_connection, SOFTPEDIA_SEARCH,
                                  ('h4', {'class': 'ln'}), ('span', {'itemprop': 'softwareVersion'}))
        f.write(str(result))

    sql_connection.close()


def main():
    parse_section()

if __name__ == '__main__':
    exit(main())

# -*- coding: utf-8 -*-
import urllib2
import sqlite3
from distutils.version import LooseVersion
import re, urlparse

from BeautifulSoup import BeautifulSoup
from html import HTML

PORTAL_NAME = 'http://soft.mydiv.net'
DOWNLOAD_COM_SEARCH = 'http://download.cnet.com/1770-20_4-0.html?platform=Windows&searchtype=downloads&query='
SOFTPEDIA_SEARCH = 'http://win.softpedia.com/dyn-search.php?search_term='

def urlEncodeNonAscii(b):
    return re.sub('[\x80-\xFF]', lambda c: '%%%02x' % ord(c.group(0)), b)

def iriToUri(iri):
    parts = urlparse.urlparse(iri)
    return urlparse.urlunparse(
        part.encode('idna') if parti==1 else urlEncodeNonAscii(part.encode('utf-8'))
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
    for raw_a in soup.findAll('td', {'class':'page'}):
        page_num_text = raw_a.text 
        if page_num_text.encode('utf-8').strip() == u'···'.encode('utf-8').strip():                    
            #print raw_a.text
            pass
        else:
            #print page_num_text
            page_num = int(page_num_text)            
            if page_nums and (page_num - page_nums[-1]) > 1:
                for i in xrange(page_nums[-1], page_num + 1):
                    pages.append(url + 'index' + str(i) + ".html")
            page_nums.append(page_num)
            pages.append(PORTAL_NAME + str(raw_a.a['href']))
                        
    pages = unique(pages)        
    pages.append(url)    
        
    for pg in pages:    
        print pg                            
        ps = BeautifulSoup(urllib2.urlopen(pg))
        for item in ps.findAll('a', {'class':'itemname'}):
            try:
                print item.contents[0].strip()
                print item.span.string
                sql_cursor.execute("INSERT INTO parsed(site, program, version) VALUES(?, ?, ?)", [pg, item.contents[0].strip(), item.span.string])
            except AttributeError as e:
                sql_connection.rollback()
                continue
            else:
                sql_connection.commit()                   
    
def compare_versions(sql_connection, search_url, list_params, ver_params, content_index = None):   
    sql_cursor = sql_connection.cursor()     
    html_output = HTML('html')    
    my_table = html_output.body.table(border='1')
    header_row = my_table.tr
    header_row.th("MyDiv")
    header_row.th("Version")
    header_row.th("Search result")
    header_row.th("Version")
    header_row.th("Url")
    
    for index, sql_row in enumerate(sql_cursor.execute("SELECT program, version, site FROM parsed")):        
        print index,
        target_name = sql_row[0]
        target_version = sql_row[1]
        target_url = sql_row[2]
        search_page_html = urllib2.urlopen(iriToUri(search_url + target_name))                        
        search_page_soup = BeautifulSoup(search_page_html)        
        search_results_soup = search_page_soup.findAll(list_params[0], list_params[1])
        
        for result in search_results_soup[:2]:
            finded_name = result.a.string
            finded_url = result.a['href']
            
#             if target_name.split(' ')[0] in str(finded_name).split(' '):
            #print " ".join(finded_name.split(' ')[:-1])                
            if target_name == " ".join(finded_name.split(' ')[:-1]):
                finded_page = urllib2.urlopen(finded_url)
                finded_page_soup = BeautifulSoup(finded_page)
                finded_version = ""
                
                if content_index:
                    finded_version = finded_page_soup.find(ver_params[0], ver_params[1]).contents[content_index].string
                else:
                    finded_version = finded_page_soup.find(ver_params[0], ver_params[1]).string                                
                
                if LooseVersion(target_version) < LooseVersion(finded_version):
                    table_row = my_table.tr
                    table_row.td(target_name)
                    table_row.td(target_version)                    
                    table_row.td(finded_name)
                    table_row.td(finded_version)
                    url_col = table_row.td
                    url_col.a(finded_name, href=finded_url)
                    print("On MyDiv %s %s, on search %s %s " % (target_name, target_version, finded_name, finded_version))                            
    return html_output
    

def main():
    sql_connection = sqlite3.connect('example.db')    
    #parse_site('http://soft.mydiv.net/win/cname47/', sql_connection)
    with open("result.html", "w") as f:
        #result = compare_versions(sql_connection, DOWNLOAD_COM_SEARCH, ('div', {'class':'result-name'}), ('tr', {'id':'specsPubVersion'}), 3)
        result = compare_versions(sql_connection, SOFTPEDIA_SEARCH, ('h4', {'class':'ln'}), ('span', {'itemprop':'softwareVersion'}))
        f.write(str(result))
        
    sql_connection.close()
    
if __name__ == '__main__':
    exit(main())
    
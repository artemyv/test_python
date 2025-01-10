import logging
import os
import re
import requests
import sys
from bs4 import BeautifulSoup
import tkinter as tk
# Add the EpubMerge folder to the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../EpubMerge/epubmerge'))) 
from epubmerge import doMerge
from datetime import datetime



# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("flibusta_downloader.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class WebPageParser:
    def __init__(self, url):
        self.url = url
        self.host = re.match(r'(https?://[^/]+)', url).group(1)
        self.page_content = None
        self.soap = None
        self.selected = None
        self.story_name = None
        self.new_part = False
        self.tags = []
        
    def fetch_page(self):
        try:
            logging.info(f"Start downloading {self.url}")
            response = requests.get(self.url)
            response.raise_for_status()
            self.page_content = response.text
            logging.info(f"Downloaded {len(self.page_content)} bytes")
        except requests.RequestException as e:
            logging.error(f"Error fetching the page: {e}")
            self.page_content = None

    def parse_page(self):
        if self.page_content is None:
            logging.warning("No content to parse.")
            print("No content to parse. Please fetch the page first.")
            return None
        self.soup = BeautifulSoup(self.page_content, 'html.parser')
        logging.debug(self.soup)
    
    def get_annotation(self,url, index, tags):
        try:
            response = requests.get(self.host + url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            main_div = soup.find('div', id='main')
            if main_div:
                annotation_tag = main_div.find('h2', text='Аннотация')
                if annotation_tag:
                    p_tag = annotation_tag.find_next('p')
                    if p_tag:
                        annotation = p_tag.get_text().strip()
                if annotation:
                    logging.info(f"Found annotation for part {index} : {annotation}")
                # get text from all a tags with class "genre" within main_div
                for a in main_div.find_all('a', class_='genre'):
                    if a.get_text() not in tags:
                        tags.append(a.get_text())
                # Find text contains "Добавлена: dd.mm.yyyy" and parse date - for example Добавлена: 04.09.2022
                found = re.search(r'Добавлена: (\d{2}\.\d{2}\.\d{4})', main_div.get_text())
                if found:
                    modified_date_str = found.group(1)
                    if modified_date_str:
                        modified = datetime.strptime(modified_date_str, '%d.%m.%Y')
                        if modified:
                            logging.info(f"Found modified date for part {index}: {modified}")
                
            return annotation, modified
        
        except requests.RequestException as e:
            logging.error(f"Error fetching the annotation: {e}")
            
    def get_story_links(self, lastUpdated):
        if self.soup is None:
            logging.warning("No content has been parsed.")
            print("No content has been parsed. Please fetch the page first and parse it.")
            return None
        main_div = self.soup.find('div', id='main')
        if(main_div is None):
            logging.error("No main div found")
            print("No main div found. Please check the URL.")
            return None
        self.story_name = main_div.find('h1').get_text().strip()
        logging.info(f"Found story name {self.story_name}")
        links = []
        tags = []
        for a in main_div.find_all('a', href=True):
            if re.fullmatch(r'/b/\d+', a['href']):
                text_before_a = a.previous_sibling.strip() if a.previous_sibling else ''
                logging.debug(f"Found part: {text_before_a} name: {a.get_text()}, url: {a['href']}")
                annotation, modified_date = self.get_annotation(a['href'], text_before_a, tags)
                if lastUpdated:
                    modified = modified_date > lastUpdated
                else:
                    modified = True
                    
                links.append({'url': a['href'], 'text': a.get_text(), 'index': text_before_a, 'annotation': annotation, 'modified': modified})
        self.tags = tags
        return links

    def show_links_in_listbox(self, links):
        def move_up():
            selected_indices = listbox.curselection()
            for index in selected_indices:
                if index == 0:
                    continue
                text = listbox.get(index)
                listbox.delete(index)
                listbox.insert(index - 1, text)
                listbox.selection_set(index - 1)

        def move_down():
            selected_indices = listbox.curselection()
            for index in reversed(selected_indices):
                if index == listbox.size() - 1:
                    continue
                text = listbox.get(index)
                listbox.delete(index)
                listbox.insert(index + 1, text)
                listbox.selection_set(index + 1)

        def store_selected():
            selected_indices = listbox.curselection()
            self.selected = [entries[listbox.get(i)] for i in selected_indices]
            root.destroy()

        root = tk.Tk()
        root.title("Story Links")

        listbox = tk.Listbox(root, selectmode=tk.EXTENDED, width=100, height=20)
        listbox.pack()
        entries = {}
        for link in links:
            text = f"{link['index']} - {link['text']}"
            if link['modified']:
                text += " *"
            listbox.insert(tk.END, text)
            entries[text] = link

        # Select all entries by default
        listbox.select_set(0, tk.END)

        btn_up = tk.Button(root, text="Move Up", command=move_up)
        btn_up.pack(side=tk.LEFT)

        btn_down = tk.Button(root, text="Move Down", command=move_down)
        btn_down.pack(side=tk.LEFT)

        btn_show = tk.Button(root, text="Ok", command=store_selected)
        btn_show.pack(side=tk.LEFT)

        root.mainloop()
        
    def handle_selected(self):
        if self.selected is None:
            logging.warning("No links have been selected.")
            print("No links have been selected. Please select some links first.")
            return None
        folder_name = re.sub(r'[\\/*?:"<>|]', "", self.story_name)
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)
        logging.info(f"Created folder: {folder_name}")
        files = []
        annotation = "";
        for link in self.selected:
            logging.info(f"Processing link: {link['url']} - {link['text']}")
            files.append(self.fetch_part(link['url'], folder_name))
            annotation += f"{link['index']} - {link['text']}\n\n"
            part_annotation = link.get('annotation', '')
            if part_annotation not in annotation:
                annotation += part_annotation + '\n\n'
            
        self.use_epubmerge(folder_name, files, annotation)
        
    def fetch_part(self, base_url, folder):
        try:
            part_url = self.host + base_url + '/epub'
            file_name = base_url.split('/')[-1] + '.epub'
            file_path = os.path.join(folder, file_name)
            
            logging.info(f"Downloading {part_url} to {file_path}")
            if os.path.exists(file_path):
                logging.info(f"File {file_name} already exists in {folder} - skip downloading")
#                logging.info(f"\tif you still want to redownload file - please remove local file and run script again")
                return file_path
            response = requests.get(part_url)
            response.raise_for_status()
            with open(file_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)
            logging.info(f"Saved {file_name} to {folder}")
            self.new_part = True
            return file_path
        except requests.RequestException as e:
            logging.error(f"Error fetching the part: {e}")
            return None
       
    # Test the epubmerge import
        files = []
    def use_epubmerge(self, name,  files, annotation):
        try:
            doMerge(
                f"{name}.epub", 
                files,
                [],
                name,
                annotation ,
                self.tags,
                ['ru'],
            True,
            True,
            False,
            False,
            False,
            None,
            False,
            self.url)
            
            
            
            print(f"{name}.epub created" )
            logging.info(f"Merged {name}.epub created")
            
        except Exception as e:
            print(f"Error importing epubmerge: {e}")

def parse_date(date_str):
    try:
        return datetime.strptime(date_str, '%d %b %Y')
    except ValueError as e:
        logging.error(f"Error parsing date: {e}")
        return None

if len(sys.argv) < 2:
    print("Usage: python flibusta_downloader.py <URL> [LastUpdated]")
    sys.exit(1)

url = sys.argv[1] # https://flibusta.is/s/65539
if len(sys.argv) > 2:
    lastUpdated=sys.argv[2]

if lastUpdated:
    lastUpdatedDate = parse_date(lastUpdated)
    if lastUpdatedDate:
        logging.info(f"Parsed last updated date: {lastUpdatedDate}")
    else:
        logging.warning("Failed to parse last updated date.")
parser = WebPageParser(url)
parser.fetch_page()
parser.parse_page()

links = parser.get_story_links(lastUpdatedDate)
parser.show_links_in_listbox(links)
parser.handle_selected()

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



# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("flibusta_downloader.log"),
        logging.StreamHandler()
    ]
)

class WebPageParser:
    def __init__(self, url):
        self.url = url
        self.page_content = None
        self.soap = None
        self.selected = None
        self.story_name = None
        self.new_part = False
        
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
        
    def get_story_links(self):
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
        for a in main_div.find_all('a', href=True):
            if re.fullmatch(r'/b/\d+', a['href']):
                text_before_a = a.previous_sibling.strip() if a.previous_sibling else ''
                links.append({'url': a['href'], 'text': a.get_text(), 'index': text_before_a})
                logging.debug(f"Found part: {text_before_a} name: {a.get_text()}, url: {a['href']}")
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
            listbox.insert(tk.END, text)
            entries[text] = link

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
        for link in self.selected:
            logging.info(f"Processing link: {link['url']} - {link['text']}")
            files.append(self.fetch_part(link['url'], folder_name))
        self.use_epubmerge(folder_name, files)
        
    def fetch_part(self, base_url, folder):
        try:
            part_url = re.match(r'(https?://[^/]+)', self.url).group(1) + base_url + '/epub'
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
    def use_epubmerge(self, name,  files):
        try:
            doMerge(f"{name}.epub", files)
            print(f"{name}.epub created" )
            logging.info(f"Merged {name}.epub created")
            
        except Exception as e:
            print(f"Error importing epubmerge: {e}")

if len(sys.argv) != 2:
    print("Usage: python flibusta_downloader.py <URL>")
    sys.exit(1)

url = sys.argv[1] # https://flibusta.is/s/65539

parser = WebPageParser(url)
parser.fetch_page()
parser.parse_page()

links = parser.get_story_links()
parser.show_links_in_listbox(links)
parser.handle_selected()

import logging
import os
import re
import requests
import sys
from bs4 import BeautifulSoup
import tkinter as tk
from urllib.parse import urljoin
from datetime import datetime

# Add the EpubMerge folder to the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../EpubMerge/epubmerge'))) 
from epubmerge import doMerge

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
    """
    A class to parse web pages from the Flibusta website, extract story parts, and download them.

    Attributes:
        url (str): The URL of the web page to parse.
        host (str): The base part of the URL. Used to construct parts URLs
        page_content (str): The content of the story web page.
        soup (BeautifulSoup): The BeautifulSoup object for parsing story HTML.
        selected (list): The list of selected story parts.
        story_name (str): The name of the story.
        new_part (bool): Flag indicating if the part was modified since LastUpdated.
        tags (list): The list of tags associated with the story.
        error (bool): Flag indicating if an error occurred.
        result (str): The result message.
    """
    def __init__(self, url, lastUpdate):
        self.url = url
        self.lastUpdated = lastUpdate
        self.host = re.match(r'(https?://[^/]+)', url).group(1)
        self.page_content = None
        self.soup = None
        self.selected = None
        self.story_name = None
        self.tags = []
        self.error = False
        self.result = None
     
    def process(self):
        self.update_status("Reading page", "black")
        self.fetch_page()
        if not self.error:
            self.parse_page()
        if not self.error:
            links = self.get_story_links()
        if not self.error:
            self.show_links_in_listbox(links)
   
    def update_status(self, message, color):
        error_label.config(text=message, fg=color)
        root.update_idletasks()
                        
    def fetch_page(self):
        try:
            logging.info(f"Start downloading {self.url}")
            response = requests.get(self.url)
            response.raise_for_status()
            self.page_content = response.text
            logging.info(f"Downloaded {len(self.page_content)} bytes")
        except requests.RequestException as e:
            logging.error(f"Error fetching the page: {e}")
            self.error = True
            self.result=f"Error fetching the page: {e}"
            self.page_content = None
            self.update_status(f"Error fetching the page: {e}", "red")

    def parse_page(self):
        if self.page_content is None:
            self.error = True
            self.result="No content to parse. Please provide valid url."
            logging.warning("No content to parse.")
            return None
        self.soup = BeautifulSoup(self.page_content, 'html.parser')
        if not self.soup:
            self.error = True
            self.result="Failed to parse the content. Please provide valid url."
            logging.error("Failed to parse the content.")
            return None
        logging.info("Page content has been parsed.")

    def get_story_links(self):
        if self.soup is None:
            logging.warning("No content has been parsed.")
            self.error = True
            self.result="No content has been parsed. Please provide valid url."
            return None
        main_div = self.soup.find('div', id='main')
        if(main_div is None):
            logging.error("No main div found")
            self.error = True
            self.result="No main div found. Please check the URL."
            return None
        self.story_name = main_div.find('h1').get_text().strip()
        logging.info(f"Found story name {self.story_name}")
        links = []
        tags = []
        for a in main_div.find_all('a', href=True):
            if re.fullmatch(r'/b/\d+', a['href']):
                text_before_a = a.previous_sibling.strip() if a.previous_sibling else ''
                logging.debug(f"Found part: {text_before_a} name: {a.get_text()}, url: {a['href']}")
                part_details = self.get_part_details(a['href'], text_before_a, tags)
                annotation = None
                modified = True # if not sure - mark part as modified
                if part_details:
                    annotation = part_details.get('annotation', None)
                    modified_date = part_details.get('modified', None)
                    if self.lastUpdated and modified_date:
                        modified = modified_date > self.lastUpdated
                    else:
                        modified = True
                links.append({'url': a['href'], 'text': a.get_text(), 'index': text_before_a, 'annotation': annotation, 'modified': modified})
        self.tags = tags
        return links
            
    def get_part_details(self,url, index, tags):
        try:
            response = requests.get(self.host + url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            main_div = soup.find('div', id='main')
            modified = None
            annotation = None
            if main_div:
                annotation_tag = main_div.find('h2', text='Аннотация')
                if annotation_tag:
                    p_tag = annotation_tag.find_next('p')
                    if p_tag:
                        annotation = p_tag.get_text().strip()
                if annotation:
                    logging.debug(f"Found annotation for part {index} : {annotation}")
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
            return {'annotation': annotation, 'modified': modified}
        
        except requests.RequestException as e:
            logging.error(f"Error fetching the part_details: {e}")
            return None
            

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
            self.handle_selected()

        listbox_frame = tk.Frame(root)
        listbox_frame.grid(row=4, columnspan=2, padx=10, pady=10)

        listbox = tk.Listbox(listbox_frame, selectmode=tk.EXTENDED, width=100, height=20)
        listbox.pack(side=tk.LEFT)
        entries = {}
        for link in links:
            text = f"{link['index']} - {link['text']}"
            if link['modified']:
                text += " *"
            listbox.insert(tk.END, text)
            entries[text] = link

        # Select all entries by default
        listbox.select_set(0, tk.END)

        btn_frame = tk.Frame(listbox_frame)
        btn_frame.pack(side=tk.RIGHT, fill=tk.Y)

        btn_up = tk.Button(btn_frame, text="Up", command=move_up)
        btn_up.pack(fill=tk.X)

        btn_down = tk.Button(btn_frame, text="Down", command=move_down)
        btn_down.pack(fill=tk.X)

        btn_show = tk.Button(btn_frame, text="Save story epub", command=store_selected)
        btn_show.pack(fill=tk.X)

    def handle_selected(self):
        if self.selected is None:
            self.handle_no_selection()
            return None
        folder_name = self.create_folder()
        story_details = self.process_links(folder_name)
        self.merge_story_parts(story_details)
 
    def handle_no_selection(self):
        logging.warning("No links have been selected.")
        self.error = True
        self.result = "No links have been selected. Please select some links to download."

    def create_folder(self):
        folder_name = re.sub(r'[\\/*?:"<>|]', "", self.story_name)
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)
        return folder_name

    def process_links(self, folder_name):
        annotation = ""
        files = []
        for link in self.selected:
            logging.info(f"Processing link: {link['url']} - {link['text']}")
            part_file = self.fetch_part(link['url'], folder_name)
            if not part_file:
                logging.warning(f"Failed to fetch part: {link['url']}")
                #todo: break further processing?
                continue
            files.append(part_file)
            annotation += f"{link['index']} - {link['text']}\n\n"
            part_annotation = link.get('annotation', '')
            if part_annotation not in annotation:
                annotation += part_annotation + '\n\n'
        return {'name': folder_name, 'annotation': annotation, 'files': files}
        
    def fetch_part(self, base_url, folder):
        part_url = urljoin(self.host, base_url + '/epub')
        file_name = base_url.split('/')[-1] + '.epub'
        file_path = os.path.join(folder, file_name)
        
        if self.check_file_exists(file_path, file_name, folder):
            return file_path
        
        if self.download_file(part_url, file_path):
            self.new_part = True
            return file_path
        return None

    def check_file_exists(self, file_path, file_name, folder):
        logging.info(f"Downloading {file_path} to {folder}")
        if os.path.exists(file_path):
            logging.info(f"File {file_name} already exists in {folder} - skip downloading")
            return True
        return False

    def download_file(self, part_url, file_path):
        try:
            response = requests.get(part_url)
            response.raise_for_status()
            self.save_file(response, file_path)
            logging.info(f"Saved {file_path}")
            return True
        except requests.RequestException as e:
            logging.error(f"Error fetching the part: {e}")
            return False

    def save_file(self, response, file_path):
        with open(file_path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file.write(chunk)
    
    def merge_story_parts(self, story_details):   
        try:
            doMerge(
                f"{story_details['name']}.epub",
                story_details['files'],
                [],
                self.story_name,
                story_details['annotation'],
                self.tags,
                ['ru'],
                True,
                True,
                False,
                False,
                False,
                None,
                False,
                self.url
            )
            self.result = f"{story_details['name']}.epub created" 
            logging.info(f"Merged {story_details['name']}.epub created")
            
        except Exception as e:
            logging.error(f"Error merging epub: {e}")         
            self.result = f"Error merging epub: {e}"
            self.error = True
            
            
            


def parse_date(date_str):
    try:
        return datetime.strptime(date_str, '%d %b %Y')
    except ValueError as e:
        logging.error(f"Error parsing date: {e}")
        return None

    
def on_read():
    url = url_entry.get()
    lastUpdated = last_updated_entry.get()
    lastUpdatedDate = None
    if not url:
        error_label.config(text="URL is required.", fg="red")
        url_entry.config(bg="red")
        root.update_idletasks()
        return
    else:
        if not re.match(r'https?://', url):
            error_label.config(text="Invalid URL format.", fg="red")
            url_entry.config(bg="red")
            root.update_idletasks()
            return
    if lastUpdated:
        lastUpdatedDate = parse_date(lastUpdated)
        if lastUpdatedDate:
            logging.info(f"Parsed last updated date: {lastUpdatedDate}")
        else:
            logging.warning("Failed to parse last updated date.")
            error_label.config(text="Failed to parse last updated date.", fg="red")
            last_updated_entry.config(bg="red")
            root.update_idletasks()
            return
    error_label.config(text="", fg="black")
    url_entry.config(bg="white")
    last_updated_entry.config(bg="white")
    root.update_idletasks()

    parser = WebPageParser(url, lastUpdatedDate)
    parser.process()
    #if parser.error:
    #    error_label.config(text=parser.result, fg="red")
    #else:
    #    error_label.config(text=parser.result, fg="green")
    #root.update_idletasks()

def on_close():
    root.destroy()
    sys.exit(1)

root = tk.Tk()
root.title("Flibusta Downloader")

tk.Label(root, text="URL:").grid(row=0, column=0, padx=10, pady=10)
url_entry = tk.Entry(root, width=50)
url_entry.grid(row=0, column=1, padx=10, pady=10)

tk.Label(root, text="Last Updated (optional):").grid(row=1, column=0, padx=10, pady=10)
last_updated_entry = tk.Entry(root, width=50)
last_updated_entry.grid(row=1, column=1, padx=10, pady=10)

error_label = tk.Label(root, text="", fg="white")
error_label.grid(row=3, columnspan=2, padx=10, pady=10)

ok_button = tk.Button(root, text="Read story parts", command=on_read)
ok_button.grid(row=2, column=0, padx=10, pady=10)

cancel_button = tk.Button(root, text="Close", command=on_close)
cancel_button.grid(row=2, column=1, padx=10, pady=10)

root.mainloop()

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
    def __init__(self, TkRoot, url):
        self.url = url
        self.host = re.match(r'(https?://[^/]+)', url).group(1)
        self.page_content = None
        self.soup = None
        self.selected = None
        self.story_name = None
        self.new_part = False
        self.tags = []
        self.error = False
        self.result = None
        self.Tk = TkRoot
        
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

    def parse_page(self):
        if self.page_content is None:
            self.error = True
            self.result="No content to parse. Please provide valid url."
            logging.warning("No content to parse.")
            return None
        self.soup = BeautifulSoup(self.page_content, 'html.parser')
        logging.debug(self.soup)
    
    def get_annotation(self,url, index, tags):
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
            return annotation, modified
        
        except requests.RequestException as e:
            logging.error(f"Error fetching the annotation: {e}")
            
    def get_story_links(self, lastUpdated):
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
            second_form.destroy()
            self.handle_selected()

        second_form = tk.Toplevel(self.Tk)
        second_form.title("Story Links")

        listbox = tk.Listbox(second_form, selectmode=tk.EXTENDED, width=100, height=20)
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

        btn_up = tk.Button(second_form, text="Move Up", command=move_up)
        btn_up.pack(side=tk.LEFT)

        btn_down = tk.Button(second_form, text="Move Down", command=move_down)
        btn_down.pack(side=tk.LEFT)

        btn_show = tk.Button(second_form, text="Ok", command=store_selected)
        btn_show.pack(side=tk.LEFT)

        second_form.mainloop()
        
    def handle_selected(self):
        if self.selected is None:
            logging.warning("No links have been selected.")
            self.error = True
            self.result="No links have been selected. Please select some links to download."
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
        
        self.Tk.update_idletasks()
        
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
                annotation,
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
            
            
            
            self.result=f"{name}.epub created" 
            logging.info(f"Merged {name}.epub created")
            
        except Exception as e:
            self.result=f"Error importing epubmerge: {e}"
            self.error = True
            logging.error(f"Error importing epubmerge: {e}")
            
    def process(self, lastUpdatedDate):
        self.fetch_page()
        if not self.error:
            self.parse_page()
        if not self.error:
            links = self.get_story_links(lastUpdatedDate)
        if not self.error:
            self.show_links_in_listbox(links)



def parse_date(date_str):
    try:
        return datetime.strptime(date_str, '%d %b %Y')
    except ValueError as e:
        logging.error(f"Error parsing date: {e}")
        return None

    
def on_ok():
    global url, lastUpdatedDate
    url = url_entry.get()
    lastUpdated = last_updated_entry.get()
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

    lastUpdatedDate = None
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

    error_label.config(text="", fg="white")
    url_entry.config(bg="white")
    last_updated_entry.config(bg="white")
    root.update_idletasks()

    parser = WebPageParser(root, url)
    parser.process(lastUpdatedDate)
    if parser.error:
        error_label.config(text=parser.result, fg="red")
    else:
        error_label.config(text=parser.result, fg="green")

def on_cancel():
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

ok_button = tk.Button(root, text="OK", command=on_ok)
ok_button.grid(row=2, column=0, padx=10, pady=10)

cancel_button = tk.Button(root, text="Cancel", command=on_cancel)
cancel_button.grid(row=2, column=1, padx=10, pady=10)

root.mainloop()

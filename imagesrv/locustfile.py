import logging
from locust import FastHttpUser, task, events
import random
import imageBuilder

images = []

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

logging.basicConfig(
    filename='test.log',
    filemode='a',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.WARNING
)

logger = logging.getLogger(__name__)
file_handler = logging.FileHandler('july8_all_am.log')
file_handler.setLevel(logging.WARNING)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

@events.request.add_listener
def log_request(request_type, name, response_time, response_length, response, context, exception, start_time, url,
                **kwargs):
    try:
        if exception:
            logger.error(f"FAILURE: {request_type} {name} {response_time} {exception} at {start_time}")
        elif response_time > 20000:
            logger.warning(f"Long Request: {name} took {response_time} for {url} at {start_time}")
        else:
            logger.info(f"Request: {request_type} {name} {response_time}")
    except Exception as e:
        print(f"Logging error: {e}")

@events.init_command_line_parser.add_listener
def _(parser):
    parser.add_argument("--url-list", type=str, env_var="URL_LIST", default="", help="File of URLs to info.jsons")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    try:
        with open(environment.parsed_options.url_list, 'r') as fh:
            for line in fh:
                url = line.replace('\n', '')
                if not url.endswith('/info.json'):
                    print(f"Skipping {url} as it doesn't end with '/info.json'")
                else:
                    images.append(url)
        if len(images) == 0:
            environment.runner.quit()
    except Exception as error:
        print(error)
        environment.runner.quit()


def identifier(url):
    return url[:-1 * len('/info.json')]


def rndImage():
    return images[random.randint(0, len(images) - 1)]


def rndImageIdentifier():
    return identifier(rndImage())


class IIIFURLTester(FastHttpUser):
    @task(6)
    def getMiradorThumbnail(self):
        url = f"{rndImageIdentifier()}/full/,120/0/default.jpg"
        self.client.get(url, name="Mirador thumbnail")

    @task(6)
    def getUVThumbnail(self):
        url = f"{rndImageIdentifier()}/full/90,/0/default.jpg"
        self.client.get(url, name="UV thumbnail")

    @task(6)
    def getThumbnailPanel(self):
        with self.client.get(rndImage(), name="info.json") as response:
            response.encoding = "utf-8"
            info = response.json()
            defaultSize = 125  # pixels
            width = defaultSize
            height = defaultSize
            found = False
            if 'sizes' in info:
                for size in info['sizes']:
                    if size['width'] >= defaultSize and size['height'] >= defaultSize:
                        width = size['width']
                        height = size['height']
                        found = True
                        break
                if found:
                    url = imageBuilder.constructURL(info, 'full', width=width, height=height)
                else:
                    url = imageBuilder.constructURL(info, 'full', width=width, height=height, bounded=True)
            else:
                url = imageBuilder.constructURL(info, 'full', width=width, height=height, bounded=True)
            self.client.get(url, name="Thumbnail panel thumbnail")

    @task(3)
    def zoomToPoint(self):
        with self.client.get(rndImage(), name="info.json") as response:
            response.encoding = "utf-8"
            info = response.json()
            images = imageBuilder.zoomToPoint(info, random.randint(0, info['width'] - 1),
                                              random.randint(0, info['height'] - 1))
            for (region, size) in images:
                url = imageBuilder.constructURL(info, region, size=size)
                self.client.get(url, name="Zoom to point")

    @task(2)
    def virtualReading(self):
        with self.client.get(rndImage(), name="info.json") as response:
            response.encoding = "utf-8"
            info = response.json()
            url = imageBuilder.constructURL(info, 'full', width=90)
            self.client.get(url, name="Virtual Reading")
            if 'tiles' in info and type(info['tiles']) == list:
                tiles = info['tiles'][0]
                if 'scaleFactors' in tiles:
                    levels = imageBuilder.levelsWithTiles(info)
                    images = imageBuilder.tiles(info, levels[random.randint(0, len(levels) - 1)])
                    for x in range(len(images)):
                        for y in range(len(images[x])):
                            (region, size) = images[x][y]
                            url = imageBuilder.constructURL(info, region, size=size)
                            self.client.get(url, name="Virtual Reading")

    @task(1)
    def customRegion(self):
        with self.client.get(rndImage(), name="info.json") as response:
            response.encoding = "utf-8"
            info = response.json()
            width = random.randint(200, 400)
            height = random.randint(200, 400)
            x = random.randint(0, info['width'] - width)
            y = random.randint(0, info['height'] - height)
            url = imageBuilder.constructURL(info, f'{x},{y},{width},{height}', size=f"{width},{height}")
            self.client.get(url, name="Custom region")

    @task(5)
    def fullImageSized(self):
        sizes = [",200", "150,", "200,", "400,", "650,", "675,", "800,", "!1024,1024"]
        with self.client.get(rndImage(), name="info.json") as response:
            response.encoding = "utf-8"
            info = response.json()
            size = sizes[random.randint(0, len(sizes) - 1)]
            reqWidth = size.split(',')[0].replace('!', '')
            if reqWidth and int(reqWidth) < info['width']:
                return
            reqHeight = size.split(',')[1]
            if reqHeight and int(reqHeight) < info['height']:
                return
            url = f"{rndImageIdentifier()}/full/{size}/0/default.jpg"
            self.client.get(url, name="Full image scaled")

    @task(4)
    def fullImage(self):
        with self.client.get(rndImage(), name="info.json") as response:
            response.encoding = "utf-8"
            info = response.json()
            url = imageBuilder.constructURL(info, 'full', size="full")
            self.client.get(url, name="Full/full image request")

    @task(7)
    def halfScale(self):
        with self.client.get(rndImage(), name="info.json") as response:
            response.encoding = "utf-8"
            info = response.json()
            url = imageBuilder.constructURL(info, 'full', size="pct:50")
            self.client.get(url, name="Full/full image request at half scale")

    @task(8)
    def grayScale(self):
        url = f"{rndImageIdentifier()}/full/full/0/gray.jpg"
        self.client.get(url, name="Full image gray scale")

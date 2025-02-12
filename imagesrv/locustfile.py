import logging
from locust import FastHttpUser, events, task
import random
import imageBuilder

images = []

logger = logging.getLogger(__name__)

@events.init_command_line_parser.add_listener
def _(parser):
    parser.add_argument("--url-list", type=str, env_var="URL_LIST", default="", help="File of URLs to info.jsons")
    parser.add_argument("--log-file", type=str, env_var="LOG_FILE", default="default.log", help="Log file name")
    parser.add_argument("--log-level", type=str, env_var="LOG_LEVEL", default="WARNING", help="Log level")
    parser.add_argument("--tasks", type=str, env_var="TASKS", default="", help="Comma-separated list of tasks to run")

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    try:
        log_file = environment.parsed_options.log_file
        log_level = environment.parsed_options.log_level

        logging_levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }

        logging_level = logging_levels.get(log_level, logging.WARNING)

        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

        logging.basicConfig(
            filename=log_file,
            filemode='a',
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            level=logging_level
        )

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging_level)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

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

@events.request.add_listener
def log_request(request_type, name, response_time, response_length, response, context, exception, start_time, url,
                **kwargs):
    try:
        if exception:
            logger.error(f"FAILURE: {request_type} {name} {response_time} {exception} at {start_time} for {url}")
        elif response_time > 20000:
            logger.warning(f"Long Request: {name} took {response_time} for {url} at {start_time}")
        elif response_time > 1000:
            logger.warning(f"At least a second: {name} took {response_time} for {url} at {start_time}")
        else:
            logger.info(f"Request: {request_type} {name} {response_time} for {url}.")
    except Exception as e:
        print(f"Logging error: {e} for {url}")

def identifier(url):
    return url[:-1 * len('/info.json')]

def rndImage():
    return images[random.randint(0, len(images) - 1)]

def rndImageIdentifier():
    return identifier(rndImage())

class IIIFURLTester(FastHttpUser):
    tasks = []

    def getMiradorThumbnail(self):
        url = f"{rndImageIdentifier()}/full/,120/0/default.jpg"
        self.client.get(url, name="Mirador thumbnail")

    def getUVThumbnail(self):
        url = f"{rndImageIdentifier()}/full/90,/0/default.jpg"
        self.client.get(url, name="UV thumbnail")

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

    def zoomToPoint(self):
        with self.client.get(rndImage(), name="info.json") as response:
            response.encoding = "utf-8"
            info = response.json()
            images = imageBuilder.zoomToPoint(info, random.randint(0, info['width'] - 1),
                                              random.randint(0, info['height'] - 1))
            for (region, size) in images:
                url = imageBuilder.constructURL(info, region, size=size)
                self.client.get(url, name="Zoom to point")

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

    def fullImage(self):
        with self.client.get(rndImage(), name="info.json") as response:
            response.encoding = "utf-8"
            info = response.json()
            url = imageBuilder.constructURL(info, 'full', size="full")
            self.client.get(url, name="Full/full image request")

    def halfScale(self):
        url = f"{rndImageIdentifier()}/full/pct:50/0/default.jpg"
        self.client.get(url, name="Full image request at half scale")

    def grayScale(self):
        url = f"{rndImageIdentifier()}/full/full/0/gray.jpg"
        self.client.get(url, name="Full image gray scale")

    def bitonalQuality(self):
        url = f"{rndImageIdentifier()}/full/full/0/bitonal.jpg"
        self.client.get(url, name="Full image but bitonal scale")

    def mirroringFull(self):
        url = f"{rndImageIdentifier()}/full/full/!0/default.jpg"
        self.client.get(url, name="Full image but mirrored")

    def rotationRandomSize(self):
        with self.client.get(rndImage(), name="info.json") as response:
            response.encoding = "utf-8"
            info = response.json()
            size = random.choice(info['sizes'])
            rotations = (0, 90, 180, 270)
            rotation = random.choice(rotations)
            url = f"{info['@id']}/full/{size['width']},{size['height']}/{rotation}/default.jpg"
            self.client.get(url, name=f"Rotate image")

@events.init.add_listener
def _(environment, **kwargs):
    tasks_arg = environment.parsed_options.tasks
    if tasks_arg:
        tasks_to_run = tasks_arg.split(",")
    else:
        tasks_to_run = ["getMiradorThumbnail", "getUVThumbnail", "getThumbnailPanel", "zoomToPoint",
                        "virtualReading", "customRegion", "fullImageSized", "fullImage", "halfScale", "grayScale",
                        "bitonalQuality", "mirroringFull", "rotationRandomSize"]

    task_mapping = {
        "getMiradorThumbnail": IIIFURLTester.getMiradorThumbnail,
        "getUVThumbnail": IIIFURLTester.getUVThumbnail,
        "getThumbnailPanel": IIIFURLTester.getThumbnailPanel,
        "zoomToPoint": IIIFURLTester.zoomToPoint,
        "virtualReading": IIIFURLTester.virtualReading,
        "customRegion": IIIFURLTester.customRegion,
        "fullImageSized": IIIFURLTester.fullImageSized,
        "fullImage": IIIFURLTester.fullImage,
        "halfScale": IIIFURLTester.halfScale,
        "grayScale": IIIFURLTester.grayScale,
        "bitonalQuality": IIIFURLTester.bitonalQuality,
        "mirroringFull": IIIFURLTester.mirroringFull,
        "rotationRandomSize": IIIFURLTester.rotationRandomSize
    }

    IIIFURLTester.tasks = [task_mapping[task_name] for task_name in tasks_to_run]

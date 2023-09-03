"""
podcast-transcoder.py 
A script that fetches an audio podcast RSS feed, takes first
14 episodes, transcodes them to ~32kbps Opus audio, then
spits out a new RSS feed for self-hosting.
"""
import os
import csv
import feedparser
import requests
from urllib.parse import urljoin
from subprocess import call
from xml.etree.ElementTree import ElementTree, Element, SubElement

script_dir = os.path.dirname(os.path.abspath(__file__))

# podcasts.csv - subscriptions
# example:
# original_rss_url,feed_name
# https://feeds.megaphone.fm/FGTL6306430438,filmsack
# https://example.com/feed2.rss,feed2
# https://example.com/feed3.rss,feed3
#
subscriptions_file = os.path.join(script_dir, "podcasts.csv")

# output_directory, where the .opus and RSS .xml files
# will be saved, presumably a path accessible via http
# if you are subscribing to your custom feeds with a
# podcast app
output_directory = script_dir

# server_prefix, used in generating the URLs for the
# custom RSS feed; the web address to access output_dir
server_prefix = "https://revival.ezri.org/podcasts"


with open(subscriptions_file, "r") as f:
    reader = csv.DictReader(f)
    for row in reader:
        original_rss_url = row["original_rss_url"]
        feed_name = row["feed_name"]

        feed = feedparser.parse(original_rss_url)

        # Create new RSS feed
        rss = Element("rss")
        channel = SubElement(rss, "channel")

        SubElement(channel, "title").text = (
            feed.feed.get("title", "") + " (opus)"
        )
        SubElement(channel, "link").text = feed.feed.get("link", "")
        SubElement(channel, "description").text = feed.feed.get(
            "description", ""
        )

        # Add image to the channel
        image = SubElement(channel, "image")
        SubElement(image, "url").text = feed.feed.get("image", {}).get(
            "href", ""
        )
        SubElement(image, "title").text = (
            feed.feed.get("title", "") + " (opus)"
        )
        SubElement(image, "link").text = feed.feed.get("link", "")

        for entry in feed.entries[
            :14
        ]:  # Process only the most recent 14 episodes
            item = SubElement(channel, "item")
            for key in ["title", "link", "description"]:
                SubElement(item, key).text = entry.get(key, "")
            # Add the publish date
            SubElement(item, "pubDate").text = entry.get("published", "")

            if "enclosures" in entry and entry.enclosures:
                enclosure = entry.enclosures[0]
                filename = os.path.basename(enclosure["url"])
                opus_filename = os.path.splitext(filename)[0] + ".opus"

                opus_file_path = os.path.join(output_directory, opus_filename)

                # skip if file has already been transcoded
                if not os.path.exists(opus_file_path):
                    # download file
                    response = requests.get(enclosure["url"])
                    with open(
                        os.path.join(output_directory, filename), "wb"
                    ) as file:
                        file.write(response.content)

                    # transcode file to opus
                    call(
                        [
                            "ffmpeg",
                            "-i",
                            os.path.join(output_directory, filename),
                            "-b:a",
                            "32k",
                            opus_file_path,
                        ]
                    )

                # add enclosure to item
                opus_enclosure = SubElement(item, "enclosure")
                opus_enclosure.attrib = {
                    "url": urljoin(server_prefix, opus_filename),
                    "length": str(os.path.getsize(opus_file_path)),
                    "type": "audio/opus",
                }

        # save new RSS feed
        ElementTree(rss).write(
            os.path.join(output_directory, f"rss_{feed_name}.xml")
        )

# Cron script for displaying remote html (React)

## Bunch of work done on this in March of 2025

## Basics

- This script currently runs on a Raspberry pi zero w that's connected to the
  net.
- It fetches a list of frame screens to be displayed via [val.town](val.town)
- That list is then used to fetch the the next image in rotation based on which
  one is currently being displayed on the connected eink display derived from
  state.json.
- You can also tell it which frame to display using the param -F or --frame.

```shell
pip install -r requirements.txt
python fetch_and_display_image.py --frame weather
```

## Remote backend for fetching data

For ease of iteration, the backend was created on
[val.town](https://www.val.town/x/michaelwschultz/frame). There you can view
each frame and remix them if you'd like. You can view the image that will be
sent down to the pi and make any changes you'd like. You can also control the
list of images you'd like to show up on your pi so you don't have to log into
the pi to change anything once it's set up.

## Add startup process using pm2

```shell
pm2 start fetch_and_display_image.py --name fetch_and_display --no-autorestart --cron "0 7,19 * * *"
pm2 save
pm2 startup

pm2 logs fetch_and_display
```

## 3D Printing

Right now, I'm using
[this design](https://makerworld.com/en/models/787533-waveshare-7-5-inch-e-paper-case#profileId-725479).

Here's
[another design](https://www.printables.com/model/219811-waveshare-75-e-paper-case-symmetrical-borders)
if you're interested in adding a battery to your setup.

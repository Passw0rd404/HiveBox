import requests
from datetime import datetime, timedelta

url = "https://api.opensensemap.org/boxes/"

def get_avg_temp():
    count = 0.0
    boxs =  get_boxes()
    boxs = check_boxs(boxs)
    boxs_temps = get_boxes_temp(boxs)
    for temp in boxs_temps:
        temp = float(temp)
        count += temp
    avg_temp = count / len(boxs_temps)
    return round(avg_temp, 2)


def get_boxes():
    passargs = {"bbox": "13.0884,52.3382,13.7611,52.6755"}
    response = requests.get(url, params=passargs, timeout=10)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code}")
        return []

def check_boxs(states):
    ok_boxs = []
    for box in states:
        if "lastMeasurementAt" in box.keys():
            last_measurement = datetime.strptime(box["lastMeasurementAt"], "%Y-%m-%dT%H:%M:%S.%fZ")
            now_str = datetime.now().isoformat(timespec="milliseconds") + "Z"
            now = datetime.strptime(now_str, "%Y-%m-%dT%H:%M:%S.%fZ")
            if now - last_measurement <= timedelta(hours=3):
                ok_boxs.append(box["_id"])
    return ok_boxs
              

def get_boxes_temp(boxs):
    temps = []
    for box in boxs:
        response = requests.get(url + box, timeout=30)
        data = response.json()
        for sensor in data["sensors"]:
            if sensor["title"] == "Temperature":
                temps.append(sensor["lastMeasurement"]["value"])    
    return temps
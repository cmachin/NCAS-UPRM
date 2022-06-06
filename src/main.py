
import serial
import pynmea2
import csv
import numpy as np
from scipy.interpolate import griddata
import matplotlib.pyplot as plt
from matplotlib import cm
from dronekit import connect
from datetime import date
from time import sleep
import os
import basemap
import dronekit_sitl 
'''
TODO
- make scannable variable into function -> boolean
'''
# https://hacks.mozilla.org/2017/02/headless-raspberry-pi-configuration-over-bluetooth/

# 2D and 3D graphing function in Matplotlib (Contour)
def graph(lon, lat, topo, threeD = False) -> None:

    
    if(threeD):
        fig, ax1 = plt.subplots(subplot_kw={"projection": "3d"})
        fileName = "ThreeD Map.png"
    else:
        fig, ax1 = plt.subplots()     
        fileName = "TwoD Map.png"
        
    fig.set_figheight(10)
    fig.set_figwidth(15)
    xi = np.linspace(min(lon), max(lon), len(lon))
    yi = np.linspace(min(lat), max(lat), len(lat))
    
    zi = griddata((lon ,lat), topo, (xi[None,:], yi[:,None]), method='linear')

    cntr1 = ax1.contourf(xi, yi, zi, levels=30,cmap= cm.coolwarm)
    cbar = fig.colorbar(cntr1, ax=ax1)
    cbar.set_label('Depth in Feet', fontsize = 20)
    
    #uncomment to see where each sample was taken
    #ax1.plot(lon, lat, 'bo', ms=1)
    
    ax1.set(xlim=(min(lon) , max(lon)), ylim=(min(lat), max(lat)))
    
    ax1.set_title('Bathymetry Map in Parguera', fontsize = 20)
    ax1.set_xlabel('Latitude', fontsize = 20)
    ax1.set_ylabel('Longitude', fontsize = 20)
    plt.savefig("test3d.png")
    plt.show()
    
    today = date.today().strftime("%b-%d-%Y")
    plt.savefig(os.getcwd() + '/Data/Graphs/' + today + fileName)
    
    graph(lon, lat, topo, threeD=True)

def mapOverlay(lat,lon, csvpath: str, zoom=16, map_type='roadmap'):
    
    import pandas as pd
    
    from bokeh.io import output_notebook
    from bokeh.io import show
    from bokeh.plotting import gmap
    from bokeh.models import GMapOptions
    from bokeh.models import HoverTool
    from bokeh.io import export_png
    from bokeh.transform import linear_cmap
    from bokeh.palettes import Plasma256 as palette
    from bokeh.models import ColorBar
    
    df = pd.read_csv('C:/Users/dasus/Documents/NCAS-M/NCAS/Data/depth_data/Mar-25-2022.csv')

    gmap_options = GMapOptions(lat=lat, lng=lng, 
                               map_type=map_type, zoom=zoom)
    hover = HoverTool(
        tooltips = [
            ('Depth in Feet', '@Depth_in_Feet '),
            # the {0.} means that we don't want decimals
            # for 1 decimal, write {0.0}
        ]
    )
    p = gmap(api_key, gmap_options, title='Bathymetry Map Parguera', 
             width=bokeh_width, height=bokeh_height,
             tools=[hover, 'reset', 'wheel_zoom', 'pan'])
    source = ColumnDataSource(df)
    # defining a color mapper, that will map values of pricem2
    # between 2000 and 8000 on the color palette
    mapper = linear_cmap('Depth', palette, min(df.Depth), max(df.Depth))    
    # we use the mapper for the color of the circles
    center = p.circle('Longitude', 'Latitude', radius='radius', alpha=0.4, 
                      color=mapper, source=source)
    # and we add a color scale to see which values the colors 
    # correspond to 
    color_bar = ColorBar(color_mapper=mapper['transform'], 
                         location=(0,0))
    p.add_layout(color_bar, 'right')
    p.background_fill_color = None
    p.border_fill_color = None
    
    

    export_png(p, filename="plot.png") 
    return p
# Function to determines if vehicle is armed or not done with missions
def isScannable(vehicle, cmds, missionlist) -> bool:
    return vehicle.armed or cmds.next <= len(missionlist)

# Run
def run():
    # Initialize ports for pixhawk and echosounder
    _vehicle_port = '/dev/ttyACM0'
    _echosounder_port = '/dev/ttyUSB0'

    # Initialize data lists
    lat = np.array([])
    lon = np.array([])
    topo = np.array([])
    today = date.today().strftime("%b-%d-%Y")
    
    # Create and initialize csv file
    csvfile = open(os.getcwd() + '/Data/depth_data/' + today + '.csv', 'w')
    writer = csv.writer(csvfile)
    _header = ['Latitude', 'Longitude', 'Depth_in_Feet']
    writer.writerow(_header)

    # Pixhawk connection loop
    while True:
        try:
            vehicle = connect(_vehicle_port, baud=115200, heartbeat_timeout=5)
            # Download comands
            cmds = vehicle.commands
            cmds.download()
            cmds.wait_ready()
            # Initialize list of missions
            missionlist = []
            break

        except Exception as e:
            print('Could not connect to Pixhawk')
            print(e)
            continue

    # Add all commands to the list of missions
    for cmd in cmds:
        missionlist.append(cmd)

    # Sensor connection
    print("about to enter loop")
    ser = serial.Serial(_echosounder_port, baudrate=4800, timeout=2)
    row = [None, None, None]
    scannable = vehicle.armed

    ##for i in range(50): #stop deleting this

    while scannable:
        
        # Translate NMEA data to sentences
        try:
            line = ser.readline().decode('ascii', 'ignore')
            nmea_object = pynmea2.parse(line)

        except Exception:
            continue
        
        # Detect and record depth data sentences
        if nmea_object.sentence_type == 'DBT':
            
                print(f'Appending Depth Data {nmea_object.depth_feet}')
                topo = np.append(topo, float(nmea_object.depth_feet))
                row[2] = nmea_object.depth_feet
                
                
        # Detect and record location data sentences
        elif nmea_object.sentence_type == 'GGA':
            
            print(f'Appending GPS Data:  {nmea_object.latitude} {nmea_object.longitude}')
            lat = np.append(lat, nmea_object.latitude)
            lon = np.append(lon, nmea_object.longitude)
            row[0] = nmea_object.latitude
            row[1] = nmea_object.longitude
            
        print(row)

        # Write data to CSV file
        if all(row):
            print('ADDING ROW CSV')
            writer.writerow(row)
            csvfile.flush()    # Save current data to CSV
            row = [None, None, None]
            sleep(0.1)
        scannable = vehicle.armed

    print('Done with Mission ')

    # Close CSV file and EchoSounder Port
    csvfile.close()
    ser.close()
    
    # Graph CSV data
    try:
        graph(lon, lat, topo)
        mapOverlay(lat, lon, csvfile.name)
        
    except Exception as e:
        
        print(' AT least you tried graphs :|')
        row = ['could not graph', 'error', e]
        writer.writerow(row)
    


# Main function
if __name__ == '__main__':
    run()
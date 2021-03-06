""" Baseado em http://github.com/brianw/osmgeocode  
    osm.py
    Licença BSD

* Copyright (c) 1982, 1986, 1990, 1991, 1993
*      The Regents of the University of California.  All rights reserved.
*
* Redistribution and use in source and binary forms, with or without
* modification, are permitted provided that the following conditions
* are met:
* 1. Redistributions of source code must retain the above copyright
*    notice, this list of conditions and the following disclaimer.
* 2. Redistributions in binary form must reproduce the above copyright
*    notice, this list of conditions and the following disclaimer in the
*    documentation and/or other materials provided with the distribution.
* 3. All advertising materials mentioning features or use of this software
*    must display the following acknowledgement:
*      This product includes software developed by the University of
*      California, Berkeley and its contributors.
* 4. Neither the name of the University nor the names of its contributors
*    may be used to endorse or promote products derived from this software
*    without specific prior written permission.
*
* THIS SOFTWARE IS PROVIDED BY THE REGENTS AND CONTRIBUTORS ``AS IS'' AND
* ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
* IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
* ARE DISCLAIMED.  IN NO EVENT SHALL THE REGENTS OR CONTRIBUTORS BE LIABLE
* FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
* DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
* OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
* HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
* LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
* OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
* SUCH DAMAGE    
"""
import xml.sax
import copy
import networkx as nx
from math import radians, cos, sin, asin, sqrt

def download_osm(left,bottom,right,top,highway_cat):

    from urllib import urlopen
    
    try:    
        fp = urlopen( "http://www.overpass-api.de/api/xapi?way[highway=%s][bbox=%f,%f,%f,%f]"%(highway_cat,left,bottom,right,top) )
        return fp
    except:
        print ("osm data download unsuccessful")

def distancia(lon1, lat1, lon2, lat2):
    #Converte de Decimal para Radianos
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # Fórmula Haversine
    raio_terra = 6371
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    m = raio_terra * c * 1000
    return m        

def le_arquivo(arquivo, estrada=True):

    osm = OSM(arquivo)
    G = nx.DiGraph() #Grafo Direcionado
 
    for way in osm.ways.itervalues():
        
        if estrada and 'highway' not in way.tags:
            continue
        G.add_path(way.nds, id=way.id, highway = way.tags['highway'], data=way)#{str(k): type(v) for k,v in way.tags.items()})

        if 'oneway' not in way.tags and  way.tags['highway'] != 'motorway':
            G.add_path(reversed(way.nds), id=way.id, highway = way.tags['highway'], data=way)

        elif way.tags['oneway'] != 'yes' and way.tags['oneway'] != '-1' and  way.tags['highway'] != 'motorway':
            G.add_path(reversed(way.nds), id=way.id, highway = way.tags['highway'], data=way)
        
    for n_id in G.nodes_iter():
        n = osm.nodes[n_id]
        G.node[n_id] = dict(lon=n.lon,lat=n.lat)

    for i in G.edges():
        latA = G.node[i[0]]['lat']
        lonA = G.node[i[0]]['lon']
        latB = G.node[i[1]]['lat']
        lonB = G.node[i[1]]['lon']
        dist = distancia(lonA,latA,lonB,latB)
        G[i[0]][i[1]]['weight'] = dist
        G[i[0]][i[1]]['label'] = float("{0:.2f}".format(dist))

    for i in G.nodes():
        nd_label = str(G.node[i]['lat']) + ',' + str(G.node[i]['lon'])
        G.node[i]['label'] = nd_label
    return G

class Node:
    def __init__(self, id, lon, lat):
        self.id = id
        self.lon = lon
        self.lat = lat
        self.tags = {}
        
class Way:
    def __init__(self, id, osm):
        self.osm = osm
        self.id = id
        self.nds = []
        self.tags = {}
        
    def split(self, dividers):
        
        def slice_array(ar, dividers):
            for i in range(1,len(ar)-1):
                if dividers[ar[i]]>1:
                    left = ar[:i+1]
                    right = ar[i:]
                    
                    rightsliced = slice_array(right, dividers)
                    
                    return [left]+rightsliced
            return [ar]

        slices = slice_array(self.nds, dividers)

        ret = []
        i=0
        for slice in slices:
            littleway = copy.copy( self )
            littleway.id += "-%d"%i
            littleway.nds = slice
            ret.append( littleway )
            i += 1
            
        return ret
        
class OSM:
    def __init__(self, arquivo):

        nodes = {}
        ways = {}
        
        superself = self
        
        class OSMHandler(xml.sax.ContentHandler):
            @classmethod
            def setDocumentLocator(self,loc):
                pass
            
            @classmethod
            def startDocument(self):
                pass
                
            @classmethod
            def endDocument(self):
                pass
                
            @classmethod
            def startElement(self, name, attrs):
                if name=='node':
                    self.currElem = Node(attrs['id'], float(attrs['lon']), float(attrs['lat']))
                elif name=='way':
                    self.currElem = Way(attrs['id'], superself)
                elif name=='tag':
                    self.currElem.tags[attrs['k']] = attrs['v']
                elif name=='nd':
                    self.currElem.nds.append( attrs['ref'] )
                
            @classmethod
            def endElement(self,name):
                if name=='node':
                    nodes[self.currElem.id] = self.currElem
                elif name=='way':
                    ways[self.currElem.id] = self.currElem
                
            @classmethod
            def characters(self, chars):
                pass
 
        xml.sax.parse(arquivo, OSMHandler)
        
        self.nodes = nodes
        self.ways = ways

        #count times each node is used
        node_histogram = dict.fromkeys( self.nodes.keys(), 0 )
        for way in self.ways.values():
            if len(way.nds) < 2:       #if a way has only one node, delete it out of the osm collection
                del self.ways[way.id]
            else:
                for node in way.nds:
                    node_histogram[node] += 1
        
        #use that histogram to split all ways, replacing the member set of ways
        new_ways = {}
        for id, way in self.ways.iteritems():
            split_ways = way.split(node_histogram)
            for split_way in split_ways:
                new_ways[split_way.id] = split_way
        self.ways = new_ways

d1Lat = -22.919167
d1Lon = -43.249569
d2Lat = -22.911933
d2Lon = -43.241286

G=le_arquivo(download_osm(d1Lon,d1Lat,d2Lon,d2Lat,"motorway|trunk|primary|secondary|tertiary|unclassified|track|service|residential"))

pos=nx.circular_layout(G)
A=nx.drawing.nx_agraph.to_agraph(G)
A.write('grafo.dot')




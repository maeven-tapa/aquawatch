"""Shared validation for API, web forms, and Django admin zone edits."""
import math
from django.core.exceptions import ValidationError

ENVELOPE = [(120.712,14.37),(120.743,14.36),(120.800,14.40),
            (120.820,14.44),(120.820,14.46),(120.712,14.46)]

def cross(a,b,c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])

def inside_water(point):
    return all(cross(a,ENVELOPE[(i+1)%len(ENVELOPE)],point)>=0 for i,a in enumerate(ENVELOPE))

def point_in_polygon(point, points):
    inside = False
    x,y = point
    for i,(ax,ay) in enumerate(points):
        bx,by = points[(i+1)%len(points)]
        if (ay>y)!=(by>y) and x < (bx-ax)*(y-ay)/(by-ay)+ax:
            inside = not inside
    return inside

def validate_geometry(boundary, latitude, longitude):
    if not isinstance(boundary,list) or not 3<=len(boundary)<=100:
        raise ValidationError('Use 3–100 boundary vertices, without repeating the first vertex.')
    points=[]
    for vertex in boundary:
        if not isinstance(vertex,dict) or set(vertex)!={'lat','lng'}:
            raise ValidationError('Each boundary vertex must contain lat and lng.')
        lat,lng=vertex['lat'],vertex['lng']
        if any(type(n) not in (int,float) or not math.isfinite(n) for n in (lat,lng)):
            raise ValidationError('Coordinates must be finite numbers.')
        if not inside_water((lng,lat)):
            raise ValidationError('The entire zone must stay inside the offshore fishing area, away from land.')
        points.append((lng,lat))
    if len(set(points))!=len(points):
        raise ValidationError('Boundary vertices must be distinct.')
    for i,a in enumerate(points):
        b=points[(i+1)%len(points)]
        for j in range(i+1,len(points)):
            if j==i+1 or (i==0 and j==len(points)-1): continue
            c,d=points[j],points[(j+1)%len(points)]
            if (max(a[0],b[0])>=min(c[0],d[0]) and max(c[0],d[0])>=min(a[0],b[0]) and
                max(a[1],b[1])>=min(c[1],d[1]) and max(c[1],d[1])>=min(a[1],b[1]) and
                cross(a,b,c)*cross(a,b,d)<=0 and cross(c,d,a)*cross(c,d,b)<=0):
                raise ValidationError('Boundary edges must not cross or touch each other.')
    if any(type(n) not in (int,float) or not math.isfinite(n) for n in (latitude,longitude)):
        raise ValidationError('Zone center must have valid coordinates.')
    if not point_in_polygon((longitude,latitude),points):
        raise ValidationError('The center pin must be inside the zone boundary.')
    origin=points[0]
    sx=111320*math.cos(math.radians(latitude))
    xy=[((x-origin[0])*sx,(y-origin[1])*111320) for x,y in points]
    area=abs(sum(x*xy[(i+1)%len(xy)][1]-xy[(i+1)%len(xy)][0]*y for i,(x,y) in enumerate(xy)))/2
    if area<100:
        raise ValidationError('Zone area must be at least 100 square meters.')
    return area

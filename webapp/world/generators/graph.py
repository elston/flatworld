import numpy as np

from ..map import Center, Edge, Corner
from .utils.voronoi import voronoi_finite_polygons


def key(p1, p2=None):
    if p2 is None:
        return tuple(p1)
    return tuple(sorted([tuple(p1), tuple(p2)]))


class VoronoiGraph:

    def generate(self, map_obj):
        points = map_obj.points
        regions = voronoi_finite_polygons(points, bbox=map_obj.bbox)

        centers = {}
        corners = {}
        edges = {}

        for point in points:
            centers[key(point)] = Center(point)

        region_edges = []
        for region in regions:
            cell_edges = []
            for i in range(len(region) - 1):
                cell_edges.append((region[i], region[i + 1]))

            region_edges.append(cell_edges)

            for vertice in region:
                if key(vertice) not in corners:
                    corner = Corner(vertice)
                    corner.border = (
                        vertice[0] == 0 or vertice[0] == 1 or vertice[1] == 0 or vertice[1] == 1
                    )
                    corners[key(vertice)] = corner

        for point_index, cell_edges in enumerate(region_edges):
            point = points[point_index]
            center = centers[key(point)]

            for p1, p2 in cell_edges:
                if key(p1, p2) not in edges:
                    corner1 = corners[key(p1)]
                    corner2 = corners[key(p2)]
                    edge = Edge((corner1, corner2))
                    corner1.protrudes.append(edge)
                    corner2.protrudes.append(edge)
                    corner1.adjacent.append(corner2)
                    corner2.adjacent.append(corner1)
                    edge.border = corner1.border and corner2.border
                    edges[key(p1, p2)] = edge
                else:
                    edge = edges[key(p1, p2)]

                center.borders.append(edge)
                edge.centers.append(center)

        for point_index, region_vertices in enumerate(regions):
            point = points[point_index]
            center = centers[key(point)]

            for vertice in region_vertices:
                corner = corners[key(vertice)]
                center.corners.append(corner)
                corner.touches.append(center)

        for edge in edges.values():
            assert 1 <= len(edge.centers) <= 2
            if len(edge.centers) == 1:
                edge.centers[0].border = True
            else:
                edge.centers[0].neighbors.append(edge.centers[1])
                edge.centers[1].neighbors.append(edge.centers[0])

        map_obj.centers = list(centers.values())
        map_obj.edges = list(edges.values())
        map_obj.corners = list(corners.values())

    def imporove_corners(self, map_obj):
        """
        Although Lloyd relaxation improves the uniformity of polygon
        sizes, it doesn't help with the edge lengths. Short edges can
        be bad for some games, and lead to weird artifacts on
        rivers. We can easily lengthen short edges by moving the
        corners, but **we lose the Voronoi property**.  The corners are
        moved to the average of the polygon centers around them. Short
        edges become longer. Long edges tend to become shorter. The
        polygons tend to be more uniform after this step.
        """
        new_corners = []

        for corner in map_obj.corners:
            if corner.border:
                new_corners.append(corner.point)
            else:
                new_corners.append(
                    np.mean(np.array([c.point for c in corner.touches]), axis=0)
                )

        for i, corner in enumerate(map_obj.corners):
            corner.point = new_corners[i]

        # fix edges' midpoint
        for edge in map_obj.edges:
            edge.midpoint = [
                (edge.corners[0].point[0] + edge.corners[1].point[0]) / 2,
                (edge.corners[0].point[1] + edge.corners[1].point[1]) / 2,
            ]

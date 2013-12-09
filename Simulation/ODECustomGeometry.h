#ifndef ODE_CUSTOM_MESH_H
#define ODE_CUSTOM_MESH_H

#include <geometry/AnyGeometry.h>
#include <ode/common.h>
using namespace Geometry;

struct CustomGeometryData
{
  ///The object pointed to must live throughout the duration of the ODE
  ///custom geometry.
  AnyCollisionGeometry3D* geometry;
  ///The *extra* collision margin to the used with the geometry.  If the
  ///geometry already has padding, this amount will be added on to detect
  ///collisions.
  Real outerMargin;
  ///The translation from the geometry local frame to the ODE frame.
  ///i.e., the negation of the local COM vector.
  Vector3 odeOffset;
};


dGeomID dCreateCustomGeometry(AnyCollisionGeometry3D* geom,Real outerMargin=0);
CustomGeometryData* dGetCustomGeometryData(dGeomID o);
void InitODECustomGeometry();

#endif


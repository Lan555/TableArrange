import numpy as np
from simple_3dviz.renderables.textured_mesh import Material, TexturedMesh
from simple_3dviz.behaviours.keyboard import SnapshotOnKey
from simple_3dviz import Scene, Mesh
from simple_3dviz.behaviours.io import SaveFrames, SaveGif
from simple_3dviz.behaviours.movements import CameraTrajectory
from simple_3dviz.behaviours.trajectory import Circle
from simple_3dviz.utils import render
from simple_3dviz.window import show
from simple_3dviz.utils import save_frame
import pyrr
import os


def render_image(renderables, color, mode, frame_path=None):
    size=(512,512),
    scene = Scene(size=(256,256), background=(1,1,1,1))
    scene.up_vector = (0,0,1)
    scene.camera_target = (0,0,0)
    scene.camera_position = (-2.0,-2.0,-2.0)
    scene.light = (-2.0,-2.0,-2.0)
    scene.camera_matrix = pyrr.Matrix44.orthogonal_projection(
        left=-3.1, right=3.1, bottom=-3.1, top=3.1, near=0.1, far=6
    )

    if color is not None:
        try:
            color[0][0]
        except TypeError:
            color = [color]*len(renderables)
    else:
        color = [None]*len(renderables)

    scene.clear()
    for r, c in zip(renderables, color):
        if isinstance(r, Mesh) and c is not None:
            r.mode = mode
            r.colors = c
        scene.add(r)
    scene.render()
    if frame_path is not None:
        save_frame(frame_path, scene.frame)

    return np.copy(scene.frame)

def render_gif(renderables, frame_path):
    render(
        renderables,
        [
            CameraTrajectory(
                Circle((0, 0, 0), (0.0, 0.8, -2.0), (0, -1, 0)),
                speed=1/180
            ),
            SaveGif(frame_path)
        ],
        180,
        camera_position=(0.0, 0.8, -2.0),
        light=(0,)*3,
        background=(1,)*4,
        up_vector=(0, 1, 0)
)

def get_floor_plan(floor_plan, floor_textures):
    
    vertices, faces = floor_plan
    #vertices = vertices - floor_plan_centroid
    uv = np.copy(vertices[:, [0, 2]])
    uv -= uv.min(axis=0)
    uv /= 0.2  # repeat every 30cm
    texture = np.random.choice(floor_textures)
    print(os.path.join(texture,"texture.png"))
    floor = TexturedMesh.from_faces(
        vertices=vertices,
        uv=uv,
        faces=faces,
        material=Material.with_texture_image(os.path.join(texture,"texture.png"))
    )
    return [floor]

def raw_model_path(path_to_models, model_jid):
        return os.path.join(
            path_to_models,
            model_jid,
            "raw_model.obj"
        )

def z_angle(rotation, ref = [0, 0, 1]):
        # See BaseThreedFutureModel._transform for the origin of the following
        # code.
        
        axis = np.cross(ref, rotation[1:])
        theta = np.arccos(np.dot(ref, rotation[1:]))*2

        if np.sum(axis) == 0 or np.isnan(theta):
            return 0

        #assert np.dot(axis, [1, 0, 1]) == 0
        assert 0 <= theta <= 2*np.pi

        if theta >= np.pi:
            theta = theta - 2*np.pi

        return np.sign(axis[1]) * theta

def furniture_renderables(
        pos,
        rot,
        model_jid,
        file_path, 
        with_bboxes=False,
        offset = [[0, 0, 0]]
    ):
        #offset = [[0, 0, 0]]
        renderables = [
            mesh_renderable(
                offset=offset, position=pos[i], rot=rot[i], model_jid=model_jid[i], file_path=file_path
            )
            for i in range(len(model_jid))
        ]
        #if with_bboxes:
        #    for f in bboxes:
        #        renderables += [f.bbox_renderable(offset=offset)]
        return renderables

def mesh_renderable(
        offset=[[0, 0, 0]],
        position=[0, 0, 0],
        file_path="",
        model_jid="",
        rot=[[0, 0, 0]]
    ):
        m = TexturedMesh.from_file(raw_model_path(file_path, model_jid))
        m.scale([1,1,1])
        # Extract the predicted affine transformation to position the
        # mesh
        theta = z_angle(rot)
        R = np.zeros((3, 3))
        R[0, 0] = np.cos(theta)
        R[0, 2] = -np.sin(theta)
        R[2, 0] = np.sin(theta)
        R[2, 2] = np.cos(theta)
        R[1, 1] = 1.

        # Apply the transformations in order to correctly position the mesh
        m.affine_transform(R=R, t=position)
        m.affine_transform(t=offset)
        return m

if __name__ == "__main__":
    # [0, sin, 0, cos]
    #pos = [[-0.3,0,0], [0,0,0.3], [0,0,0], [-0.45,0,0]]
    #rot = [[0,-0.92387953251,0,0.38268343236], [0,-0.2588190451,0,0.96592582628], [0,-0.2588190451,0,0.96592582628], [0,0,0,1]]
    #model_jid = ["0b8aed6a0ceb460db0716c642605be74", "ae35ae9f063848408ee24e90ce797e64", "167de6283da94ebea5598ec4cb75607a", "9ed8083420f5474bb281c797fd557efa"]
    pos = [[0.2,0,0.2], [0.4,0,0.2], [-0.25,0,0.2], [-0.1,0,0.2], [0,0,0.6], [-0.5,0,0.6], [0.45,0,0.6], [2.45,0,0.6]]
    rot = [[0,0.866158094405463, 0, -0.4997701026431024], [0,0,1,0], [0,0.7073882691671998, 0, -0.706825181105366], [0,0,0,1], [0,0,0,1],[0,0,0,1], [0,0,0,1], [0,0.7073882691671998,0,-0.706825181105366]]
    model_jid = ["a5cce410728140c492855a109f219ac1", "9ed8083420f5474bb281c797fd557efa", "728a8071ac15443692164300a9e42270", "119d5abe285545559f2a8b25760f7354", "4c119ebcdd9843e7b1f14b6f67ef20d7", "aae3a509b9d541f890fb69b913822679", "78186f4073dd417e95c75e98fb0c717a", "ab7f8673d9f74145b5e2294511e59e04"]
    #pos = [[0.3,0,0.2], [-0.1,0,0.5], [0.3,0,0.6], [-0.1,0,0.2], [0.7,0,-0.1], [0.7,0,0.2], [-0.1,0,-0.1],[0.7,0,0.5],[0.3,0,-0.5]]
    #rot = [[0,0.9659601685383986, 0, -0.258690844053802], [0,0,1,0], [0,0,0,1], [0,0,1,0], [0,0,0,1], [0,0,0,1], [0,0.7073882691671998, 0, -0.706825181105366],[0,0,0,1],[0,0,0,1],[0,0,0,1]]
    #model_jid = ["49211ba2343e45e8b0c50102f5ca91ec", "c27ada0a7f4e42f98789c4ff213227f1", "181d97bf1b464d14bc4318e7e1ff80b4", "0168cd50033c4e34b21ee2cff4d81d7c", "c27ada0a7f4e42f98789c4ff213227f1", "0168cd50033c4e34b21ee2cff4d81d7c", "c38e796688bd49e3a03ff2d57a2f1ed5", "c38e796688bd49e3a03ff2d57a2f1ed5", "6c1dd565e5e349e7867f82e18fa15f7e"]

    file_path = "D:\\3d-dataset\\TableArrange\\test"
    path_to_floor_plan_textures = "d:\\3d-dataset\\3D-FRONT\\3D-FRONT-texture-temp"

    renderables = furniture_renderables(
                pos, rot, model_jid, file_path, offset = [[-0, 0, -0.6]]
            )
    behaviours = []

    vertices = np.array([
        [ 1.0,0,      -1.0],
        [-1.0,0,      1.0],
        [-1.0,0,      -1.0],
        [-1.0,0,      1.0],
        [ 1.0,0,      -1.0],
        [ 1.0,0,      1.0]
    ])
    faces = np.array([
        [0, 2, 1],
        [3, 5, 4]
    ])

    floor_plan = get_floor_plan(
        [vertices*0.65, faces],
        [
            os.path.join(path_to_floor_plan_textures, fi)
            for fi in os.listdir(path_to_floor_plan_textures)
        ])
    renderables += floor_plan

    """
    path_to_image = "{}/{}_".format(args.output_directory, s.uid)
    behaviours += [SaveFrames(path_to_image+"{:03d}.png", 1)]
    render_image(
        renderables,
        color=None,
        mode="shading",
        frame_path=path_to_image
    )
    """
    path_to_gif = "{}/{}_".format(file_path, 1) + ".gif"
    render_gif(
        renderables,
        frame_path=path_to_gif
    )
    
    show(
        renderables,
        behaviours=behaviours+[SnapshotOnKey()],
        size=(512,512),
        camera_position=(0,4,0), #,(-2.0,-2.0,-2.0)
        camera_target=(0,0,0),
        light=(-12.0,-2.0,-2.0),
        up_vector=(0,0,1), #(0,0,-1),
        background=(1,1,1,1) #(0,0,0,1)
    )
    
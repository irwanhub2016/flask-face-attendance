from flask import Flask, flash, render_template, request, session, redirect, url_for, Response, jsonify
import mysql.connector
import cv2
from PIL import Image
import numpy as np
import os
import time
from datetime import date
import pdb
import re

app = Flask(__name__)
app.secret_key = 'ibnu123'
 
cnt = 0
pause_cnt = 0
justscanned = False
global status_keluar
status_keluar = False

mydb = mysql.connector.connect(
    host="localhost",
    user="root",
    passwd="",
    database="flask_db"
)
mycursor = mydb.cursor()
 
 
# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< Generate dataset >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
def generate_dataset(nbr):
    face_classifier = cv2.CascadeClassifier("/Users/irwansyarifudin/Documents/python/fc-flask/resources/haarcascade_frontalface_default.xml")
 
    def face_cropped(img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_classifier.detectMultiScale(gray, 1.3, 5)
        # scaling factor=1.3
        # Minimum neighbor = 5
 
        if faces == ():
            return None
        for (x, y, w, h) in faces:
            cropped_face = img[y:y + h, x:x + w]
        return cropped_face
 
    cap = cv2.VideoCapture(0)
 
    mycursor.execute("select ifnull(max(img_id), 0) from img_dataset")
    row = mycursor.fetchone()
    lastid = row[0]
 
    img_id = lastid
    max_imgid = img_id + 100
    count_img = 0
 
    while True:
        ret, img = cap.read()
        if face_cropped(img) is not None:
            count_img += 1
            img_id += 1
            face = cv2.resize(face_cropped(img), (200, 200))
            face = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
 
            file_name_path = "dataset/"+nbr+"."+ str(img_id) + ".jpg"
            cv2.imwrite(file_name_path, face)
            cv2.putText(face, str(count_img), (50, 50), cv2.FONT_HERSHEY_COMPLEX, 1, (0, 255, 0), 2)
 
            mycursor.execute("""INSERT INTO `img_dataset` (`img_id`, `img_person`) VALUES
                                ('{}', '{}')""".format(img_id, nbr))
            mydb.commit()
 
            frame = cv2.imencode('.jpg', face)[1].tobytes()
            yield (b'--frame\r\n'b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
 
            if cv2.waitKey(1) == 13 or int(img_id) == int(max_imgid):
                break
                cap.release()
                cv2.destroyAllWindows()
 
 
# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< Train Classifier >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
@app.route('/train_classifier/<nbr>')
def train_classifier(nbr):
    dataset_dir = "/Users/irwansyarifudin/Documents/python/fc-flask/dataset"
 
    path = [os.path.join(dataset_dir, f) for f in os.listdir(dataset_dir)]
    faces = []
    ids = []
 
    for image in path:
        img = Image.open(image).convert('L');
        imageNp = np.array(img, 'uint8')
        id = int(os.path.split(image)[1].split(".")[1])
 
        faces.append(imageNp)
        ids.append(id)
    ids = np.array(ids)
 
    # Train the classifier and save
    clf = cv2.face.LBPHFaceRecognizer_create()
    clf.train(faces, ids)
    clf.write("classifier.xml")
 
    return redirect('/')
 
 
# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< Face Recognition >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
def face_recognition(absen_type,userid):  # generate frame by frame from camera
    def draw_boundary(img, classifier, scaleFactor, minNeighbors, color, text, clf):
        gray_image = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        features = classifier.detectMultiScale(gray_image, scaleFactor, minNeighbors)
 
        global justscanned
        global pause_cnt
 
        pause_cnt += 1
 
        coords = []
 
        for (x, y, w, h) in features:
            cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)
            id, pred = clf.predict(gray_image[y:y + h, x:x + w])
            confidence = int(100 * (1 - pred / 300))
 
            if confidence > 70 and not justscanned:
                global cnt
                cnt += 1
 
                n = (100 / 30) * cnt
                # w_filled = (n / 100) * w
                w_filled = (cnt / 30) * w
 
                cv2.putText(img, str(int(n))+' %', (x + 20, y + h + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (153, 255, 255), 2, cv2.LINE_AA)
 
                cv2.rectangle(img, (x, y + h + 40), (x + w, y + h + 50), color, 2)
                cv2.rectangle(img, (x, y + h + 40), (x + int(w_filled), y + h + 50), (153, 255, 255), cv2.FILLED)
 
                mycursor.execute("select a.img_person, b.prs_name, b.prs_skill "
                                 "  from img_dataset a "
                                 "  left join guru b on a.img_person = b.prs_nbr "
                                 " where img_id = " + str(id))
                row = mycursor.fetchone()
                pnbr = row[0]
                pname = row[1]
                pskill = row[2]
 
                if int(cnt) == 30:
                    cnt = 0
                    if absen_type == 'masuk':
                        mycursor.execute("insert into accs_hist (accs_date, accs_prsn, accs_added) values('"+str(date.today())+"', '" + pnbr + "', now())")
                    else:
                        mycursor.execute("SELECT * FROM accs_hist WHERE DATE_FORMAT(accs_added, '%Y-%m-%d') = CURDATE() and accs_prsn =%s", (userid, ))
                        check_absen_masuk = mycursor.fetchall()
                        if check_absen_masuk:
                            mycursor.execute("UPDATE accs_hist SET accs_date_out = now() WHERE accs_prsn = '" + userid + "' AND DATE_FORMAT(accs_added, '%Y-%m-%d') = curdate();")
                        else:
                            mycursor.execute("insert into accs_hist (accs_date_out, accs_prsn) values('"+str(date.today())+"', '" + pnbr + "', now())")

                    mydb.commit()
 
                    cv2.putText(img, pname + ' | ' + pskill, (x - 10, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (153, 255, 255), 2, cv2.LINE_AA)
                    time.sleep(1)
 
                    justscanned = True
                    pause_cnt = 0
                    status = 'success'
                
            else:
                if not justscanned:
                    cv2.putText(img, 'TIDAK DIKETAHUI', (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2, cv2.LINE_AA)
                else:
                    cv2.putText(img, ' ', (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2,cv2.LINE_AA)
 
                if pause_cnt > 80:
                    justscanned = False
 
            coords = [x, y, w, h]
        return coords
 
    def recognize(img, clf, faceCascade):
        coords = draw_boundary(img, faceCascade, 1.1, 10, (255, 255, 0), "Face", clf)
        return img
 
    faceCascade = cv2.CascadeClassifier("/Users/irwansyarifudin/Documents/python/fc-flask/resources/haarcascade_frontalface_default.xml")
    clf = cv2.face.LBPHFaceRecognizer_create()
    clf.read("classifier.xml")
 
    wCam, hCam = 400, 400
 
    cap = cv2.VideoCapture(0)
    cap.set(3, wCam)
    cap.set(4, hCam)

    while True:
        global status
        ret, img = cap.read()
        img = recognize(img, clf, faceCascade)

        frame = cv2.imencode('.jpg', img)[1].tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')
 
        key = cv2.waitKey(1)
        if key == 27:
            break
    
    return redirect(url_for('login_guru'))
 
@app.route('/')
def home():
    # Check if user is loggedin
    if 'loggedin' in session:
        # User is loggedin show them the home page
        mycursor.execute("select prs_nbr, prs_name, prs_skill, prs_active, prs_added from guru")
        data = mycursor.fetchall()
        return render_template('index.html', data=data, mesage = 'Already login')
        # return render_template('user.html', mesage = 'Already login')
    # User is not loggedin redirect to login page
    return redirect(url_for('login'))

@app.route('/riwayat_absen')
def riwayat_absen():
    # Check if user is loggedin
    if 'loggedin' in session:
        mycursor.execute("select a.accs_id, a.accs_prsn, b.prs_name, b.prs_skill, a.accs_added, a.accs_date_out "
                        "  from accs_hist a "
                        "  left join guru b on a.accs_prsn = b.prs_nbr "
                        " order by 1 desc")
        data = mycursor.fetchall()
        return render_template('guru.html', data=data, source = 'admin')

    # User is not loggedin redirect to login page
    return redirect(url_for('login'))

@app.route('/home_guru')
def home_guru():
    # Check if user is loggedin
    if 'loggedin' in session:
        mycursor.execute("select a.accs_id, a.accs_prsn, b.prs_name, b.prs_skill, a.accs_added, a.accs_date_out "
                        "  from accs_hist a "
                        "  left join guru b on a.accs_prsn = b.prs_nbr "
                        " where a.accs_prsn =%s"
                        " order by 1 desc", (session['prs_nbr'], ))
        data = mycursor.fetchall()
        return render_template('guru.html', data=data)

    # User is not loggedin redirect to login page
    return redirect(url_for('login_guru'))

@app.route('/addprsn')
def addprsn():
    mycursor.execute("select ifnull(max(prs_nbr) + 1, 101) from guru")
    row = mycursor.fetchone()
    nbr = row[0]
    # print(int(nbr))
 
    return render_template('addprsn.html', newnbr=int(nbr))
 
@app.route('/addprsn_submit', methods=['POST'])
def addprsn_submit():
    prsnbr = request.form.get('txtnbr')
    prsname = request.form.get('txtname')
    prsemail = request.form.get('txtemail')
    prspassword = request.form.get('txtpassword')
    prsskill = request.form.get('optskill')
 
    mycursor.execute("""INSERT INTO `guru` (`prs_nbr`, `prs_name`, `prs_skill`, `email`, `password`) VALUES
                    ('{}', '{}', '{}', '{}', '{}')""".format(prsnbr, prsname, prsskill, prsemail, prspassword))
    mydb.commit()
 
    # return redirect(url_for('home'))
    return redirect(url_for('vfdataset_page', prs=prsnbr))
 
@app.route('/vfdataset_page/<prs>')
def vfdataset_page(prs):
    return render_template('gendataset.html', prs=prs)
 
@app.route('/vidfeed_dataset/<nbr>')
def vidfeed_dataset(nbr):
    #Video streaming route. Put this in the src attribute of an img tag
    return Response(generate_dataset(nbr), mimetype='multipart/x-mixed-replace; boundary=frame')
 
@app.route('/video_feed/<absen_type>',methods=['GET'])
def video_feed(absen_type):
    # Video streaming route. Put this in the src attribute of an img tag
    if 'loggedin' in session:
        return Response(face_recognition(absen_type,session['prs_nbr']), mimetype='multipart/x-mixed-replace; boundary=frame')
    
    return redirect(url_for('login_guru'))

# @app.route('/fr_page')
# def fr_page():
#     if 'loggedin' in session:
#         """Video streaming home page."""
#         mycursor.execute("select a.accs_id, a.accs_prsn, b.prs_name, b.prs_skill, a.accs_added "
#                         "  from accs_hist a "
#                         "  left join guru b on a.accs_prsn = b.prs_nbr "
#                         " where a.accs_date = curdate() and a.accs_prsn =%s"
#                         " order by 1 desc", (session['prs_nbr'], ))
#         data = mycursor.fetchall()
#         pdb.set_trace()
#         print("Saat absen keluar: " + str(status_keluar))
#         return render_template('fr_page.html', data=data)

    # User is not loggedin redirect to login page
    return redirect(url_for('login_guru'))
 
@app.route('/countTodayScan')
def countTodayScan():
    mydb = mysql.connector.connect(
        host="localhost",
        user="root",
        passwd="",
        database="flask_db"
    )
    mycursor = mydb.cursor()
 
    mycursor.execute("select count(*) "
                     "  from accs_hist "
                     " where accs_added is NOT NULL and DATE_FORMAT(accs_added, '%Y-%m-%d') = CURDATE() and accs_prsn =%s", (session['prs_nbr'], ))

    # mycursor.execute("select count(*) "
    #                  "  from accs_hist "
    #                  " where accs_date = curdate() ")
    row = mycursor.fetchone()
    rowcount = row[0]
 
    return jsonify({'rowcount': rowcount})

@app.route('/countTodayScanOut')
def countTodayScanOut():
    mydb = mysql.connector.connect(
        host="localhost",
        user="root",
        passwd="",
        database="flask_db"
    )
    mycursor = mydb.cursor()

    mycursor.execute("select count(*) "
                     "  from accs_hist "
                     " where accs_date_out is NOT NULL and DATE_FORMAT(accs_date_out, '%Y-%m-%d') = CURDATE() and accs_prsn =%s", (session['prs_nbr'], ))
    row = mycursor.fetchone()
    rowcount = row[0]
 
    return jsonify({'rowcount': rowcount}) 
 
@app.route('/loadData', methods = ['GET', 'POST'])
def loadData():
    mydb = mysql.connector.connect(
        host="localhost",
        user="root",
        passwd="",
        database="flask_db"
    )
    mycursor = mydb.cursor()
 
    mycursor.execute("select a.accs_id, a.accs_prsn, b.prs_name, b.prs_skill, date_format(a.accs_added, '%H:%i:%s') "
                     "  from accs_hist a "
                     "  left join guru b on a.accs_prsn = b.prs_nbr "
                     " where a.accs_date = curdate() "
                     " order by 1 desc")
    data = mycursor.fetchall()
 
    return jsonify(response = data)

# @app.route('/')
# def home():
#     # Check if user is loggedin
#     if 'loggedin' in session:
#         # User is loggedin show them the home page
#         return render_template('user.html', mesage = 'Already login')
#     # User is not loggedin redirect to login page
#     return redirect(url_for('login'))

@app.route('/login', methods =['GET', 'POST'])
def login():
    if 'loggedin' in session:
        # User is loggedin show them the home page
        mycursor.execute("select prs_nbr, prs_name, prs_skill, prs_active, prs_added from guru")
        data = mycursor.fetchall()
        return render_template('index.html', data=data, mesage = 'Already login')
        # return render_template('user.html', mesage = 'Already login')
        # User is not loggedin redirect to login page
        # return redirect(url_for('login'))
    else:
        mesage = ''
        if request.method == 'POST' and 'email' in request.form and 'password' in request.form:
            email = request.form['email']
            password = request.form['password']
            # cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            mycursor.execute('SELECT * FROM admin WHERE email =%s AND password =%s', (email, password, ))
            user = mycursor.fetchone()

            if user:
                session['loggedin'] = True
                session['userid'] = user[0]
                session['name'] = user[1]
                session['email'] = user[2]
                mesage = 'Logged in successfully !'
                mycursor.execute("select prs_nbr, prs_name, prs_skill, prs_active, prs_added from guru")
                data = mycursor.fetchall()
                return render_template('index.html', data=data, mesage = mesage)
            else:
                mesage = 'Please enter correct email / password !'
        return render_template('login.html', mesage = mesage)

@app.route('/login_guru', methods =['GET', 'POST'])
def login_guru():
    if 'loggedin' in session:
        # User is loggedin show them the home page
        # mycursor.execute('select prs_nbr, prs_name, prs_skill, prs_active, prs_added from guru where prs_nbr =%s', (session['prs_nbr'], ))
        return redirect(url_for('home_guru'))

        # return render_template('user.html', mesage = 'Already login')
        # User is not loggedin redirect to login page
        # return redirect(url_for('login'))
    else:
        mesage = ''
        if request.method == 'POST' and 'email' in request.form and 'password' in request.form:
            email = request.form['email']
            password = request.form['password']
            # cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            mycursor.execute('SELECT * FROM guru WHERE email =%s AND password =%s', (email, password, ))
            user = mycursor.fetchone()
            # pdb.set_trace()
            if user:
                session['loggedin'] = True
                session['prs_nbr'] = user[0]
                session['prs_name'] = user[1]
                session['email'] = user[2]
                mesage = 'Logged in successfully !'
                # mycursor.execute('select prs_nbr, prs_name, prs_skill, prs_active, prs_added from guru where prs_nbr =%s', (session['prs_nbr'], ))
                mycursor.execute("select a.accs_id, a.accs_prsn, b.prs_name, b.prs_skill, a.accs_added, a.accs_date_out "
                                "  from accs_hist a "
                                "  left join guru b on a.accs_prsn = b.prs_nbr "
                                " where a.accs_prsn =%s"
                                " order by 1 desc", (session['prs_nbr'], ))
                data = mycursor.fetchall()
                return render_template('guru.html', data=data, mesage = mesage)
            else:
                mesage = 'Please enter correct email / password !'
        return render_template('login_guru.html', mesage = mesage)

@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('userid', None)
    session.pop('email', None)
    return redirect(url_for('login'))

@app.route('/logout_guru')
def logout_guru():
    session.pop('loggedin', None)
    session.pop('prs_nbr', None)
    session.pop('prs_name', None)
    session.pop('email', None)
    return redirect(url_for('login_guru'))

@app.route('/register', methods =['GET', 'POST'])
def register():
    mesage = ''
    if request.method == 'POST' and 'name' in request.form and 'password' in request.form and 'email' in request.form :
        userName = request.form['name']
        password = request.form['password']
        email = request.form['email']
        mycursor.execute('SELECT * FROM admin WHERE email =%s', (email, ))
        account = mycursor.fetchone()
        if account:
            mesage = 'Account already exists !'
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            mesage = 'Invalid email address !'
        elif not userName or not password or not email:
            mesage = 'Please fill out the form !'
        else:
            mycursor.execute("""INSERT INTO `admin` (`name`, `email`, `password`) VALUES
                            ('{}', '{}', '{}')""".format(userName, email, password))
            mydb.commit()
            mesage = 'You have successfully registered !'
    elif request.method == 'POST':
        mesage = 'Please fill out the form !'
    return render_template('register.html', mesage = mesage)
 
@app.route('/absen_masuk')
def absen_masuk():
    if 'loggedin' in session:
        # mycursor.execute('select prs_nbr, prs_name, prs_skill, prs_active, prs_added from guru where email =%s', (session['email'], ))
        mycursor.execute("SELECT * FROM accs_hist WHERE DATE_FORMAT(accs_added, '%Y-%m-%d') = CURDATE() and accs_prsn =%s", (session['prs_nbr'], ))
        check_date = mycursor.fetchall()
        if check_date:
            # mycursor.execute("select prs_nbr, prs_name, prs_skill, prs_active, prs_added from guru where prs_nbr=%s", (session['prs_nbr'], ))
            # data = mycursor.fetchall()
            """Video streaming home page."""
            mycursor.execute("select a.accs_id, a.accs_prsn, b.prs_name, b.prs_skill, a.accs_added, a.accs_date_out "
                            "  from accs_hist a "
                            "  left join guru b on a.accs_prsn = b.prs_nbr "
                            " where a.accs_prsn =%s"
                            " order by 1 desc", (session['prs_nbr'], ))
            data = mycursor.fetchall()
            return render_template('guru.html', data=data, mesage = 'sudah absen masuk', source = 'guru')
        else:
            """Video streaming home page."""
            mycursor.execute("select a.accs_id, a.accs_prsn, b.prs_name, b.prs_skill, a.accs_added, a.accs_date_out "
                            "  from accs_hist a "
                            "  left join guru b on a.accs_prsn = b.prs_nbr "
                            " where a.accs_prsn =%s"
                            " order by 1 desc", (session['prs_nbr'], ))
            data = mycursor.fetchall()

            return render_template('fr_page.html', data=data, type='masuk', source = 'guru')

    # User is not loggedin redirect to login page
    return redirect(url_for('login_guru'))

@app.route('/absen_keluar')
def absen_keluar():
    if 'loggedin' in session:
        mycursor.execute("SELECT * FROM accs_hist WHERE DATE_FORMAT(accs_date_out, '%Y-%m-%d') = CURDATE() and accs_prsn =%s", (session['prs_nbr'], ))
        check_date = mycursor.fetchall()
        if check_date:
            mycursor.execute("select a.accs_id, a.accs_prsn, b.prs_name, b.prs_skill, a.accs_added, a.accs_date_out "
                            "  from accs_hist a "
                            "  left join guru b on a.accs_prsn = b.prs_nbr "
                            " where a.accs_prsn =%s"
                            " order by 1 desc", (session['prs_nbr'], ))
            data = mycursor.fetchall()
            return render_template('guru.html', data=data, mesage = 'sudah absen keluar', source = 'guru')
        else:
            """Video streaming home page."""
            mycursor.execute("select a.accs_id, a.accs_prsn, b.prs_name, b.prs_skill, a.accs_added, a.accs_date_out "
                            "  from accs_hist a "
                            "  left join guru b on a.accs_prsn = b.prs_nbr "
                            " where a.accs_prsn =%s"
                            " order by 1 desc", (session['prs_nbr'], ))
            data = mycursor.fetchall()

            return render_template('fr_page_keluar.html', data=data, type='keluar', source = 'guru')

    # User is not loggedin redirect to login page
    # return redirect(url_for('login_guru'))

@app.route('/test')
def test():
    return render_template('test.html')

if __name__ == "__main__":
    app.run(host='127.0.0.1', port=1234, debug=True)

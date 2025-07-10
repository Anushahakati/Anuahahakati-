@app.route('/live_attendance')
def live_attendance():
    if 'user' not in session:
        return redirect('/')

    # Step 1: Load known faces from Drive (format: name-rollno.jpg)
    from googleapiclient.http import MediaIoBaseDownload
    import io

    def download_known_faces(folder_id):
        drive_service = build('drive', 'v3', credentials=credentials)
        results = drive_service.files().list(
            q=f"'{folder_id}' in parents and (mimeType='image/jpeg' or mimeType='image/png')",
            fields="files(id, name)").execute()
        files = results.get('files', [])
        os.makedirs("known_faces", exist_ok=True)
        known_images = []
        known_labels = []

        for file in files:
            file_id = file['id']
            file_name = file['name']
            request = drive_service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            fh.seek(0)
            img_array = np.asarray(bytearray(fh.read()), dtype=np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            if img is not None:
                known_images.append(img)
                known_labels.append(os.path.splitext(file_name)[0])  # name-rollno

        return known_images, known_labels

    # Step 2: Face Comparison using histogram similarity
    def recognize_person(face_img, known_images, known_labels):
        face_gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
        face_hist = cv2.calcHist([face_gray], [0], None, [256], [0, 256])
        face_hist = cv2.normalize(face_hist, face_hist).flatten()
        best_match = None
        best_score = 0.7
        for known_img, label in zip(known_images, known_labels):
            known_gray = cv2.cvtColor(known_img, cv2.COLOR_BGR2GRAY)
            known_hist = cv2.calcHist([known_gray], [0], None, [256], [0, 256])
            known_hist = cv2.normalize(known_hist, known_hist).flatten()
            score = cv2.compareHist(face_hist, known_hist, cv2.HISTCMP_CORREL)
            if score > best_score:
                best_score = score
                best_match = label
        return best_match

    # === MAIN ===
    print("🔁 Downloading known faces from Drive...")
    known_images, known_labels = download_known_faces('1kdtb-fm3ORGf-ZTJ75VPu5uh_e5NYOUm')  # use your folder ID

    cap = cv2.VideoCapture(0)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    detected_set = set()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)

        for (x, y, w, h) in faces:
            face_crop = frame[y:y+h, x:x+w]
            identity = recognize_person(face_crop, known_images, known_labels)
            if identity and identity not in detected_set:
                detected_set.add(identity)
                mark_attendance_google_sheet(identity.split('.')[0])  # use name-rollno only
                cv2.putText(frame, f"{identity} - Attendance Taken", (x, y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                print(f"✅ Attendance taken for {identity}")
                time.sleep(2)

        cv2.imshow("Live Attendance", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    return redirect('/dashboard')

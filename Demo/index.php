<!DOCTYPE html>
<html lang="vi">

<head>
    <meta charset="UTF-8">
    <title>📄 PDF Summarizer Demo</title>
    <link rel="stylesheet" href="style.css">
</head>

<body>
    <div class="container">
        <h2>📘 Demo Tóm tắt & Phân loại PDF</h2>
        <form id="uploadForm" enctype="multipart/form-data">
            <label for="fileUpload" class="upload-label">
                🗂️ Chọn file PDF:
            </label>
            <input type="file" name="file" id="fileUpload" accept=".pdf" required>
            <br>
            <button type="submit">🚀 Tải lên & Xử lý</button>
        </form>

        <div id="loading" class="loading" style="display:none;">
            ⏳ Đang xử lý, vui lòng chờ...
        </div>

        <div id="result" class="result" style="display:none;">
            <h3>✨ Tóm tắt:</h3>
            <pre id="summary"></pre>

            <h3>🏷️ Danh mục gợi ý:</h3>
            <pre id="category"></pre>

            <h3>🔍 Top 5 kết quả tương tự:</h3>
            <ul id="topCandidates"></ul>
        </div>
    </div>

    <script src="script.js"></script>
</body>

</html>
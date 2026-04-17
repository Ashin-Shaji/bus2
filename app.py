import google.generativeai as gem, os, uuid, pandas as pd, ast, streamlit as st #, cv2
from PIL import Image
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

os.environ["GOOGLE_API_KEY"] = 
gem.configure(api_key=os.environ["GOOGLE_API_KEY"])

# Configuration
IMAGE_FOLDER = "uploaded_images"
IMAGE_FOLDER2 = "uploaded_cam_images"
os.makedirs(IMAGE_FOLDER, exist_ok=True)
os.makedirs(IMAGE_FOLDER2, exist_ok=True)

# Initialize Google Generative AI
llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro-latest")

# Streamlit UI
st.markdown(f"<h2 style='color:blue; text-align: center;'>{'Business Card Extractor'}</h2>", unsafe_allow_html=True)
st.markdown("""<style>.stButton > button {display: block;margin: 0 auto;}</style>""", unsafe_allow_html=True)

# Check if the CSV file exists
csv_filename = "business_cards.csv"
csv_exists = os.path.exists(csv_filename)

# Initialize session state for storing JSON data
if 'json_data' not in st.session_state:
    st.session_state.json_data = {}

if 'captured_images' not in st.session_state:
    st.session_state.captured_images = []

def capture_images():
    cam = cv2.VideoCapture(0)
    cv2.namedWindow("test")
    img_counter = 0
    captured_images = []

    while True:
        ret, frame = cam.read()
        if not ret:
            st.error("Failed to grab frame")
            break

        # Show the frame in a window
        cv2.imshow("test", frame)
        k = cv2.waitKey(1)

        if k % 256 == 27:  # ESC pressed
            st.write("Escape hit, closing...")
            break
        elif k % 256 == 32:  # SPACE pressed
            img_name = f"{IMAGE_FOLDER2}/opencv_frame_{img_counter}.png"
            cv2.imwrite(img_name, frame)
            st.write(f"{img_name} written!")
            captured_images.append(img_name)
            img_counter += 1

    cam.release()
    cv2.destroyAllWindows()

    return captured_images

def display_images_with_checkboxes():
    selected_images = []
    if st.session_state.captured_images:
        for idx, img_path in enumerate(st.session_state.captured_images):
            image = Image.open(img_path)
            # col1, col2 = st.columns([1, 4])
            # with col1:
            #     # Generate a unique key using UUID
            #     checkbox_key = f"{uuid.uuid4()}"
            #     if st.checkbox("Select to delete", key=checkbox_key):
            #         selected_images.append(img_path)
            # with col2:
            #     st.image(image, caption=os.path.basename(img_path))
    
    return selected_images

def upload_images():
    # Option to upload images
    uploaded_files = st.file_uploader("Upload Images", accept_multiple_files=True, type=["jpg", "jpeg", "png"])
    if uploaded_files:
        try:
            for uploaded_file in uploaded_files:
                with open(os.path.join(IMAGE_FOLDER, uploaded_file.name), "wb") as f:
                    f.write(uploaded_file.getbuffer())
            st.success("Image(s) uploaded successfully!", icon="✅")

            # Add uploaded images to the session state
            uploaded_image_paths = [os.path.join(IMAGE_FOLDER, uploaded_file.name) for uploaded_file in uploaded_files]
            st.session_state.captured_images.extend(uploaded_image_paths)

            # Display uploaded images in a grid
            num_cols = 5
            cols = st.columns(num_cols)
            for i, image_path in enumerate(uploaded_image_paths):
                with cols[i % num_cols]:
                    image = Image.open(image_path)
                    st.image(image, caption=os.path.basename(image_path))
        except Exception as e:
            st.error("Failed to upload images.")
            st.exception(e)

# Radio button to select the image input method
option = st.radio(
    "Choose the image input method:",
    ("Scan through Camera", "Upload Images")
)

if option == "Scan through Camera":
    if st.button("Capture Images"):
        captured_image_paths = capture_images()
        
        # Extend the session state list with new captured images
        st.session_state.captured_images.extend(captured_image_paths)

    # Display captured images
    selected_images = display_images_with_checkboxes()

    # Folder for existing images when "Scan through Camera" is selected
    existing_image_folder = IMAGE_FOLDER2
else:
    upload_images()

    # Folder for existing images when "Upload Images" is selected
    existing_image_folder = IMAGE_FOLDER

st.markdown("---")
st.header("Existing Images")

# Option to choose images from an existing folder
existing_images = [f for f in os.listdir(existing_image_folder) if os.path.isfile(os.path.join(existing_image_folder, f))]

if not existing_images:
    st.caption("The folder is empty")

selected_existing_images = st.multiselect("Select Images from Existing Folder", existing_images)

# Display selected existing images in a grid
if selected_existing_images:
    try:
        image_paths = [os.path.join(existing_image_folder, image_file) for image_file in selected_existing_images]
        num_cols = 5
        cols = st.columns(num_cols)
        for i, image_path in enumerate(image_paths):
            with cols[i % num_cols]:
                image = Image.open(image_path)
                st.image(image, caption=os.path.basename(image_path))
    except Exception as e:
        st.error("Failed to display selected images.")
        st.exception(e)

# Clean up selected images
if st.button("Clean Selected Images"):
    if not selected_existing_images:
        st.error("No images selected for cleaning")
    else:
        for img_file in selected_existing_images:
            img_path = os.path.join(existing_image_folder, img_file)
            if os.path.exists(img_path):
                try:
                    os.remove(img_path)
                    st.write(f"{os.path.basename(img_path)} removed!")
                    # Update session state to reflect changes
                    if img_path in st.session_state.captured_images:
                        st.session_state.captured_images.remove(img_path)
                except PermissionError:
                    st.warning(f"Cannot delete {os.path.basename(img_path)}. It might still be in use.")
            else:
                st.warning(f"File {os.path.basename(img_path)} does not exist.")
        # Clear the checkbox selections and refresh the app
        st.experimental_rerun()

# Process selected images
if st.button("Process Selected Images"):
    if not selected_existing_images:
        st.error("Select image(s) to proceed")
    else:
        columns = ["Person name", "Company name", "Email", "Contact number"]
        all_rows = []
        st.session_state.json_data = {}  # Reset session state for new processing

        try:
            for image_file in selected_existing_images:
                image_path = os.path.join(existing_image_folder, image_file)
                if not os.path.exists(image_path):
                    st.warning(f"File {os.path.basename(image_path)} does not exist.")
                    continue

                image = Image.open(image_path)
                vision = gem.GenerativeModel('gemini-1.5-pro-latest')
                res = vision.generate_content(["""You are only a business card image recognizer, you will tell clean 'YES' if it is it else clean 'NO' """, image])
                if res.text == 'NO':
                    st.info(f"{os.path.basename(image_path)} is not a business card", icon='❗')
                    continue

                message = HumanMessage(
                    # content=[
                    #     {
                    #         "type": "text",
                    #         "text": """Carefully analyze the business card(s) and get the output in pure json format

                    #         [{"Person name": "full name of the person if exists",
                    #             "Company name": "get the full company name if exists",
                    #             "Email": "get the complete mail if exists",
                    #             "Contact number": "get every contact number if exists"}]
                    #             your response shall not contain ' ```json ' and ' ``` ' """,
                    #     },
                    #     {"type": "image_url", "image_url": image_path}
                    # ]
                    content=[
                        {
                            "type": "text",
                            "text": """Carefully analyze the business card(s) and get the output in pure json format

                            [{"Person name": "full name of the person if exists",
                                "Company name": "get the full company name if exists",
                                "Email": "get the complete mail if exists",
                                "Contact number": "get every contact number if exists"}]
                                
                            if a card has multiple person name then the output be like:
                            
                            [{"Person name": "full name of the person if exists",
                                "Person name 2": "full name of the person if exists",
                                "Company name": "get the full company name if exists",
                                "Email": "get the complete mail if exists",
                                "Contact number": "get every contact number if exists"}]
                                your response shall not contain ' ```json ' and ' ``` ' """,
                        },
                        {"type": "image_url", "image_url": image_path}
                    ]
                )

                try:
                    response = llm.invoke([message])
                    response = response.content.replace('null', 'None')#.replace('null', '')
                    extracted_data = ast.literal_eval(response)

                    rows = []
                    # for item in extracted_data:
                    #     row = {col: item.get(col, "") for col in columns}
                    #     rows.append(row)
                    # all_rows.extend(rows)
                    
                    for item in extracted_data:
                        person_name = item.get("Person name", "")
                        person_name_2 = item.get("Person name 2", "")
                        row = {
                            "Person name": f"{person_name}, {person_name_2}",
                            "Company name": item.get("Company name", ""),
                            "Email": item.get("Email", ""),
                            "Contact number": item.get("Contact number", ""),
                        }
                        rows.append(row)
                    all_rows.extend(rows)

                    # Store the extracted JSON data in session state
                    st.session_state.json_data[image_file] = extracted_data
                except Exception as e:
                    st.error(f"Failed to process image: {image_file}")
                    st.exception(e)

            try:
                df = pd.DataFrame(all_rows, columns=columns)

                # Load existing CSV if it exists and append new data
                if csv_exists:
                    existing_df = pd.read_csv(csv_filename)
                    df = pd.concat([existing_df, df], ignore_index=True)

                # Save the DataFrame back to the CSV file
                df.to_csv(csv_filename, index=False)
                st.info(f"CSV file '{csv_filename}' updated", icon="✅")
            except Exception as e:
                st.error("Failed to update CSV file.")
                st.exception(e)
        except Exception as e:
            st.error("An error occurred while processing the selected images.")
            st.exception(e)

try:
    # Create columns for placing checkboxes
    col1, col2 = st.columns([1, 4])

    # Place the first checkbox (CSV) in the first column
    with col1:
        display_csv = st.checkbox("View CSV", value=csv_exists, help="Check to display CSV data")
    # Place the second checkbox (JSON) in the second column
    with col2:
        display_json = st.checkbox("View JSON", key="display_json", help="Check to display JSON data extracted")

    # Apply custom CSS to move the checkboxes downwards
    st.markdown(
        """
        <style>
        .stCheckbox {
            display: flex;
            justify-content: flex-end;
            margin-top: 20px; /* Adjust the margin-top value as needed */
        }
        </style>
        """,
        unsafe_allow_html=True
    )
except Exception as e:
    st.error("An error occurred while setting up the checkboxes.")
    st.exception(e)
    

try:
    # Display the JSON data if the checkbox is checked
    if display_json:
        for image_file, extracted_data in st.session_state.json_data.items():
            with st.expander(f"Show JSON - {image_file}"):
                st.json(extracted_data)
except Exception as e:
    st.error("An error occurred while displaying JSON data.")
    st.exception(e)

try:
    # Display the DataFrame if the checkbox is checked
    if display_csv and csv_exists:
        df = pd.read_csv(csv_filename)
        st.markdown('##### Verify Data 📝')
        edited_df = st.data_editor(df, num_rows="dynamic", key="editor_displayed")

        # Save the edited DataFrame back to the CSV file
        edited_df.to_csv(csv_filename, index=False)
        st.markdown('##### Final Data')
        st.write(edited_df)
except Exception as e:
    st.error("An error occurred while displaying the CSV data.")
    st.exception(e)

st.stop()

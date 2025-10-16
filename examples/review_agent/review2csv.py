from review_agent.review import review2csv

if 1:
    # review_type = 'literature_review'
    input_folder_path = './input'
    review_type_id = 0
else:
    # review_type = 'automotive_article'
    # input_folder_path = r'C:\Users\linxu\OneDrive - The University of Nottingham\PEMC\251006-Ferrari_Future_Traction_PhD_Program\review\Companies\Ferrari\auto_web_pages'
    input_folder_path = r'output\raw_responses-20251016_1248'
    review_type_id = 1

output_folder_path = './output'

review2csv(input_folder_path, output_folder_path, review_type_id=review_type_id)
